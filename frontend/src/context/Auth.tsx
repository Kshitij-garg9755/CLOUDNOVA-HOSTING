import {createContext,useContext,useEffect,useState, type ReactNode} from 'react';import {api} from '../services/api';
type User={id:string;name:string;email:string;role:string};type AuthType={user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<void>;register:(name:string,email:string,password:string)=>Promise<void>;logout:()=>void};
const C=createContext<AuthType>(null!);export const useAuth=()=>useContext(C);
export function AuthProvider({children}:{children:ReactNode}){const [user,setUser]=useState<User|null>(null),[loading,setLoading]=useState(true);useEffect(()=>{api.get('/auth/me').then(r=>setUser(r.data)).catch(()=>{localStorage.removeItem('cloudnova_token')}).finally(()=>setLoading(false))},[]);
const login=async(email:string,password:string)=>{const d=new URLSearchParams({username:email,password});const r=await api.post('/auth/login',d,{headers:{'Content-Type':'application/x-www-form-urlencoded'}});localStorage.setItem('cloudnova_token',r.data.access_token);setUser((await api.get('/auth/me')).data)};
const register=async(name:string,email:string,password:string)=>{await api.post('/auth/register',{name,email,password});await login(email,password)};const logout=()=>{localStorage.removeItem('cloudnova_token');setUser(null)};
return <C.Provider value={{user,loading,login,register,logout}}>{children}</C.Provider>}
