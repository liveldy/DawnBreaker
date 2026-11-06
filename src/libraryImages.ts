export function libraryImageURL(value:string){
 const match=/^img\/([1-9]\d*)$/.exec(value);
 return match?'/api/plugins/library/images/ref/'+match[1]:value;
}
