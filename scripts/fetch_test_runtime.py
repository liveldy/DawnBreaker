"""Cache one large test-only Maven artifact through verified HTTPS downloads."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,httpx
project=Path(__file__).resolve().parents[1]
artifacts=[('org/robolectric/nativeruntime-dist-compat/1.0.19/','nativeruntime-dist-compat-1.0.19',project/'.tooling/maven/org/robolectric/nativeruntime-dist-compat/1.0.19',['.pom','.jar']),('org/robolectric/android-all-instrumented/9-robolectric-4913185-2-i7/','android-all-instrumented-9-robolectric-4913185-2-i7',project/'.tooling/robolectric-runtime',['.jar'])]
with httpx.Client(trust_env=False,timeout=60) as client:
  for path,name,directory,suffixes in artifacts:
    for suffix in suffixes:
        url='https://repo.maven.apache.org/maven2/'+path+name+suffix
        checksum=client.get(url+'.sha512')
        if not checksum.is_success:
            checksum=client.get(url.replace('repo.maven.apache.org','repo1.maven.org')+'.sha512')
        checksum.raise_for_status();expected=checksum.text.strip().split()[0]
        if len(expected)!=128 or any(c not in '0123456789abcdef' for c in expected.lower()):raise RuntimeError('Invalid official checksum')
        target=directory/(name+suffix);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and hashlib.sha512(target.read_bytes()).hexdigest()==expected:continue
        # Use a regional mirror for the large payload; the checksum stays Maven Central's.
        url=url.replace('https://repo.maven.apache.org/maven2/','https://repo.huaweicloud.com/repository/maven/')
        head=client.head(url);head.raise_for_status();size=int(head.headers['content-length'])
        partial=target.with_suffix(target.suffix+'.partial')
        def chunk(start):
            end=min(start+1024*1024,size)-1
            with client.stream('GET',url,headers={'Range':f'bytes={start}-{end}'}) as response:
                if response.status_code!=206 or response.headers.get('content-range')!=f'bytes {start}-{end}/{size}':raise RuntimeError('Test runtime range mismatch')
                data=response.read()
                if len(data)!=end-start+1:raise RuntimeError('Incomplete test runtime range')
                return start,data
        if size>1024*1024:
            done=0;last=-1
            with partial.open('wb') as stream,ThreadPoolExecutor(max_workers=4) as executor:
                stream.truncate(size)
                for future in as_completed([executor.submit(chunk,start) for start in range(0,size,1024*1024)]):
                    start,data=future.result();stream.seek(start);stream.write(data);done+=len(data)
                    percent=int(done/size*5)*20
                    if percent!=last:print('Test runtime '+str(percent)+'%',flush=True);last=percent
        else:
            response=client.get(url);response.raise_for_status();partial.write_bytes(response.content)
        if hashlib.sha512(partial.read_bytes()).hexdigest()!=expected:raise RuntimeError('Test runtime checksum mismatch')
        target.with_suffix(target.suffix+'.partial').replace(target)
        print('Verified '+target.name,flush=True)
