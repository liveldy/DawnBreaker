import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import{libraryImageURL}from'./libraryImages';
import 'katex/dist/katex.min.css';
export default function MarkdownView({text}:{text:string}){
 return <div className="markdown-view"><Markdown remarkPlugins={[remarkGfm,remarkMath]} rehypePlugins={[[rehypeKatex,{throwOnError:false,strict:false,trust:false}]]} components={{a:props=><a {...props} target="_blank" rel="noopener noreferrer"/>,img:({src,alt})=>typeof src==='string'&&libraryImageURL(src).startsWith('/api/plugins/library/')?<img src={libraryImageURL(src)} alt={alt||''} loading="lazy"/>:<span className="muted">{alt||'外部图片（未自动加载）'}</span>}}>{text}</Markdown></div>;
}
