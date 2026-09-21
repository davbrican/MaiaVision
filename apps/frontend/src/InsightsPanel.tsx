import { useEffect, useState } from 'react';

type CameraInsight = {
  camera_id: string;
  camera_name: string;
  observed_samples: number;
  visible_samples: number;
  evaluable_samples: number;
  moving_samples: number;
  activity_percent: number | null;
  last_seen_at: string | null;
};

type Insights = {
  window_minutes: number;
  sample_interval_seconds: number;
  last_detection: { camera_id: string; camera_name: string; timestamp: string } | null;
  cameras: CameraInsight[];
};

function displayedTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'medium' }) : 'Sin registros en los últimos 7 días';
}

export default function InsightsPanel() {
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [data, setData] = useState<Insights | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const response = await fetch(`/api/insights?window_minutes=${windowMinutes}`, {
          credentials: 'same-origin', cache: 'no-store',
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json() as Insights;
        if (active) { setData(result); setError(''); }
      } catch {
        if (active) setError('No se pudieron cargar los indicadores.');
      }
    }
    setData(null);
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, [windowMinutes]);

  return <section className="insights-section" aria-label="Indicadores de actividad observada">
    <div className="section-header insights-heading">
      <div><p className="eyebrow">OBSERVACIONES</p><h2>Actividad y última detección</h2></div>
      <label className="insights-selector" htmlFor="insights-window">Periodo
        <select id="insights-window" value={windowMinutes} onChange={event => setWindowMinutes(Number(event.target.value))}>
          <option value={60}>Última hora</option>
          <option value={240}>Últimas 4 horas</option>
          <option value={1440}>Últimas 24 horas</option>
        </select>
      </label>
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    {data ? <div className="insights-grid">
      <article className="panel last-seen-panel">
        <p className="eyebrow">ÚLTIMA DETECCIÓN DE PERRO</p>
        <strong className="last-seen-name">{data.last_detection?.camera_name ?? 'Todavía no hay detecciones'}</strong>
        <p className="last-seen-time">{displayedTime(data.last_detection?.timestamp ?? null)}</p>
        <p className="insights-note">Es la cámara que registró el último perro visible, no un seguimiento entre cámaras ni una localización confirmada de Maia.</p>
      </article>
      <article className="panel">
        <p className="eyebrow">MOVIMIENTO OBSERVADO POR CÁMARA</p>
        <div className="activity-list">{data.cameras.map(camera => <div className="activity-camera" key={camera.camera_id}>
          <div className="activity-line"><strong>{camera.camera_name}</strong><strong>{camera.activity_percent === null ? 'Sin datos' : `${camera.activity_percent}%`}</strong></div>
          <div className="activity-track" role={camera.activity_percent === null ? undefined : 'progressbar'}
            aria-label={camera.activity_percent === null ? undefined : `Movimiento observado en ${camera.camera_name}`}
            aria-valuenow={camera.activity_percent ?? undefined} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${camera.activity_percent ?? 0}%` }} />
          </div>
          <small>{camera.evaluable_samples} muestras evaluables · Visto: {displayedTime(camera.last_seen_at)}</small>
        </div>)}</div>
        <p className="insights-note">Porcentaje de muestras con movimiento entre las muestras evaluables donde se detectó un perro. No mide ejercicio, distancia ni minutos activos; las cámaras pueden solaparse y no se suman.</p>
      </article>
    </div> : <div className="empty">Cargando observaciones…</div>}
    <p className="insights-disclaimer">Se toma una muestra por cámara cada 10 segundos cuando YOLO está activo. Sin detección puede significar oclusión, falta de luz o ausencia; no implica que Maia haya salido. No detectamos emociones ni conductas con objetos en esta versión.</p>
  </section>;
}
