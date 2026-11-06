import axios from 'axios';
export const api=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL||import.meta.env.VITE_API_URL||'http://localhost:8000/api',timeout:12000});
api.interceptors.request.use(c=>{const t=localStorage.getItem('cloudnova_token');if(t)c.headers.Authorization=`Bearer ${t}`;return c});
api.interceptors.response.use(r=>r,e=>{const msg=e.response?.data?.detail||'CloudNova API is unavailable. Please try again shortly.';return Promise.reject(new Error(typeof msg==='string'?msg:'Request failed'))});
