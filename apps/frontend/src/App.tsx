import { FormEvent, useCallback, useEffect, useState } from 'react';

type Camera = { id: string; name: string; online: boolean; status: string; seen_at: string | null };
type Event = { id: number; camera_id: string; timestamp: string; event: string; status: string };

const labels: Record<string, string> = {
  appearance: 'Perro detectado', disappearance: 'Detección perdida',
  motion_start: 'Movimiento detectado', motion_stop: 'Movimiento finalizado',
};

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api' + url, { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) {
    let message = `Error HTTP ${response.status}`;
    try { message = (await response.json()).detail || message; } catch { /* Non-JSON response */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function CameraCard({ camera, large = false }: { camera: Camera; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [camera.id, camera.online]);
  return <article className={'camera-card ' + (large ? 'large' : '')}>
    <div className="camera-header"><strong>{camera.name}</strong><span className={'dot-label ' + (camera.online ? 'online' : '')}>{camera.online ? '● En directo' : '○ Sin señal'}</span></div>
    <div className="camera-screen">
      {camera.online && !failed ? <img src={`/api/cameras/${encodeURIComponent(camera.id)}/stream`} alt={`Vídeo en directo: ${camera.name}`} onError={() => setFailed(true)}/> :
        <div className="offline"><span className="offline-icon">◉</span><strong>{failed ? 'No se ha podido reproducir' : 'Cámara desconectada'}</strong><small>Comprueba la conexión del agente</small></div>}
    </div>
    <footer><span>{camera.online ? camera.status : 'Esperando señal'}</span><small>{camera.seen_at ? new Date(camera.seen_at).toLocaleTimeString('es-ES') : 'Nunca conectada'}</small></footer>
  </article>;
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setPending(true);
    try {
      await api('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
      setPassword(''); onLogin();
    } catch (problem) { setError(problem instanceof Error ? problem.message : 'No se pudo iniciar sesión'); }
    finally { setPending(false); }
  }
  return <main className="login-layout"><form className="login-box" onSubmit={submit}>
    <div className="brand-icon">🐾</div><p className="eyebrow">MONITORIZACIÓN PRIVADA</p><h1>Bienvenido a <em>MaiaVision</em></h1>
    <p className="muted">Tus cámaras y los eventos de Maia, en un único lugar seguro.</p>
    <label htmlFor="username">Usuario</label><input id="username" name="username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required />
    <label htmlFor="password">Contraseña</label><input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
    {error && <p className="error" role="alert">{error}</p>}
    <button className="primary" disabled={pending}>{pending ? 'Comprobando…' : 'Acceder al dashboard →'}</button>
    <p className="privacy">🔒 Acceso privado · Sin grabación de vídeo por defecto</p>
  </form></main>;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [selected, setSelected] = useState('all');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const [cameraData, eventData] = await Promise.all([api<Camera[]>('/cameras'), api<Event[]>('/events?limit=25')]);
      setCameras(cameraData); setEvents(eventData); setError('');
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Error de conexión');
    }
  }, []);

  useEffect(() => {
    api('/me').then(() => setAuthenticated(true)).catch(() => setAuthenticated(false));
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    void refresh();
    const interval = window.setInterval(() => { void refresh(); }, 5000);
    return () => window.clearInterval(interval);
  }, [authenticated, refresh]);

  async function logout() {
    try { await api('/logout', { method: 'POST' }); }
    finally { setAuthenticated(false); setCameras([]); setEvents([]); }
  }

  if (authenticated === null) return <div className="boot">🐾 MaiaVision</div>;
  if (!authenticated) return <Login onLogin={() => setAuthenticated(true)} />;

  const visible = selected === 'all' ? cameras : cameras.filter(camera => camera.id === selected);
  const live = cameras.filter(camera => camera.online).length;
  const currentEvents = selected === 'all' ? events : events.filter(event => event.camera_id === selected);

  return <div className="app-shell">
    <header className="topbar"><div className="topbrand"><span className="small-brand">🐾</span><div><strong>Maia<span>Vision</span></strong><small>SMART PET MONITORING</small></div></div><div className="top-actions"><span className="connected"><i />{live}/{cameras.length} cámaras conectadas</span><button className="ghost" onClick={() => { void logout(); }}>Cerrar sesión</button></div></header>
    <main className="dashboard">
      <section className="intro"><div><p className="eyebrow">PANEL DE CONTROL</p><h1>Tu casa, <em>siempre cerca.</em></h1><p className="muted">Monitoriza las cámaras y consulta los movimientos observados. Los estados son estimaciones visuales, no diagnósticos.</p></div><div className="metric"><span>Cámaras activas</span><strong>{live}<small> / {cameras.length}</small></strong><i className="metric-line" /></div></section>
      {error && <div className="error-banner" role="alert">{error} <button onClick={() => { void refresh(); }}>Reintentar</button></div>}
      <section className="section-header"><div><p className="eyebrow">CÁMARAS</p><h2>Vista en directo</h2></div><span className="hint">Vista JPEG · {cameras.length} fuentes configuradas</span></section>
      <nav className="tabs" aria-label="Seleccionar cámara"><button className={selected === 'all' ? 'active' : ''} onClick={() => setSelected('all')}>Todas</button>{cameras.map(camera => <button key={camera.id} className={selected === camera.id ? 'active' : ''} onClick={() => setSelected(camera.id)}>{camera.name}{camera.online && <span className="mini-dot" />}</button>)}</nav>
      {visible.length ? <div className={'camera-grid ' + (visible.length === 1 ? 'single' : '')}>{visible.map(camera => <CameraCard key={camera.id} camera={camera} large={visible.length === 1}/>)}</div> : <div className="empty">No hay cámaras para esta vista.</div>}
      <section className="lower-grid"><article className="panel"><div className="panel-heading"><div><p className="eyebrow">ACTIVIDAD</p><h2>Últimos eventos</h2></div><span className="hint">Actualización cada 5 s</span></div>{currentEvents.length ? <div className="events">{currentEvents.slice(0, 12).map(event => <div className="event" key={event.id}><span className="event-bullet"/><div><strong>{labels[event.event] || event.event}</strong><small>{cameras.find(camera => camera.id === event.camera_id)?.name || event.camera_id} · {event.status}</small></div><time>{new Date(event.timestamp).toLocaleTimeString('es-ES')}</time></div>)}</div> : <div className="empty">Todavía no hay eventos. Aparecerán cuando el detector observe cambios.</div>}</article><article className="panel about"><p className="eyebrow">INFORMACIÓN</p><h2>Cómo funciona</h2><p>El agente procesa fotogramas en tu ordenador o Raspberry Pi y envía vistas JPEG reducidas y eventos al servidor.</p><p>El vídeo no se graba ni se almacena por defecto; los eventos se conservan siete días. «Sin detección» no significa que Maia haya salido de la habitación.</p><div className="info-pill">🔐 Acceso mediante sesión privada</div><div className="info-pill">📷 Compatible con webcam, Android e IP</div><div className="info-pill">⚡ Vista ligera: no equivale a vídeo HD de 30 FPS</div></article></section>
      <footer className="site-footer">MaiaVision · Hecho para vigilar actividad observable, respetando la privacidad.</footer>
    </main>
  </div>;
}
