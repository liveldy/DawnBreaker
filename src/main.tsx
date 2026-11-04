import React from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/instrument-sans/400.css';
import '@fontsource/instrument-sans/500.css';
import '@fontsource/instrument-sans/600.css';
import '@fontsource/instrument-serif/400.css';
import App from './App';
import './styles.css';
import './admin.css';

class Boundary extends React.Component<{children:React.ReactNode},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<main className="fatal"><h1>页面暂时未能打开</h1><p>你的记录已保存在账户中。请刷新页面重试。</p><button onClick={()=>location.reload()}>刷新页面</button></main>:this.props.children;}
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><Boundary><App/></Boundary></React.StrictMode>);

import './collection.css';
import './client-updates.css';
import './update-mobile-fixes.css';
import './repairs.css';
