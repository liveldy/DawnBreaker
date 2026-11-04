from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'src/App.tsx';s=p.read_text(encoding='utf-8')
s=s.replace('createContext, useContext, ','').replace('Circle }','Circle, Bot, LockKeyhole, Radar }')
start=s.index('type Context=');end=s.index('const ICONS:',start)
s=s[:start]+s[end:]
s=s.replace("import VoiceButton from './VoiceButton';","""import VoiceButton from './VoiceButton';
import {AppContext,useApp}from './context';
import Avatar from './Avatar';
import ProfileAvatar from './ProfileAvatar';
import LibraryPage from './LibraryPage';
import ConstellationPage from './ConstellationPage';
import VaultPage from './VaultPage';
import AtlasPage from './AtlasPage';
import './workspace.css';""")
s=s.replace('Music2,BookOpen,Download};','Music2,BookOpen,Download,Bot,LockKeyhole,Radar};')
s=s.replace('<span className="avatar">{boot.user.nickname.slice(0,1)}</span>','<Avatar user={boot.user}/>').replace('<span className="avatar large">{boot.user.nickname.slice(0,1)}</span>','<Avatar user={boot.user} className="large"/>').replace('<span className="avatar profile-avatar">{boot.user.nickname.slice(0,1)}</span>','<ProfileAvatar/>')
s=s.replace('downloader:DownloaderPage};','downloader:DownloaderPage,library:LibraryPage,constellation:ConstellationPage,vault:VaultPage,atlas:AtlasPage};')
p.write_text(s,encoding='utf-8')
