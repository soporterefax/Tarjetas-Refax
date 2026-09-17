const API_URL = window.REFAX_CONFIG.API_URL.replace(/\/$/, "");

function getToken(){ return localStorage.getItem("refax_token"); }
function getRole(){ return localStorage.getItem("refax_role"); }
function logout(){ localStorage.removeItem("refax_token"); localStorage.removeItem("refax_role"); localStorage.removeItem("refax_username"); window.location.href="index.html"; }

async function api(path, options={}){
  const headers = {"Content-Type":"application/json", ...(options.headers || {})};
  const token = getToken();
  if(token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${path}`, {...options, headers});
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if(response.status === 401 && token){ logout(); throw new Error("Tu sesión expiró"); }
  if(!response.ok) throw new Error(data.error || "Ocurrió un error");
  return data;
}

function requireRole(role){
  if(!getToken() || getRole() !== role){ window.location.href="index.html"; return false; }
  return true;
}
