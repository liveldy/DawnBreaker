import {createContext,useContext} from 'react';
import type{Bootstrap}from'./api';
export type Context={boot:Bootstrap;refresh:()=>Promise<void>;notify:(message:string)=>void;action:(fn:()=>Promise<any>)=>Promise<boolean>;busy:boolean;offline:boolean};
export const AppContext=createContext<Context>(null!);
export const useApp=()=>useContext(AppContext);
