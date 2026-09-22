import { useEffect, useRef, useState } from 'react';

export type Camera = {
  id: string;
  name: string;
  online: boolean;
  status: string;
  seen_at: string | null;
};

type Props = {
  camera: Camera;
  large: boolean;
  onSelect: (id: string) => void;
  streamRevision: number;
};

/** The stream and snapshot stay behind the existing authenticated, same-origin API. */
export default function CameraCard({ camera, large, onSelect, streamRevision }: Props) {
  const cardRef = useRef<HTMLElement | null>(null);
  const [failed, setFailed] = useState(false);
  const [nativeFullscreen, setNativeFullscreen] = useState(false);
  const [fallbackFullscreen, setFallbackFullscreen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [snapshotError, setSnapshotError] = useState('');
  const fullscreen = nativeFullscreen || fallbackFullscreen;

  useEffect(() => {
    setFailed(false);
    setSnapshotError('');
  }, [camera.id, camera.online, streamRevision]);

  useEffect(() => {
    const syncFullscreen = () => setNativeFullscreen(document.fullscreenElement === cardRef.current);
    document.addEventListener('fullscreenchange', syncFullscreen);
    return () => document.removeEventListener('fullscreenchange', syncFullscreen);
  }, []);

  useEffect(() => {
    if (!fallbackFullscreen) return;
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setFallbackFullscreen(false);
    };
    document.addEventListener('keydown', onEscape);
    return () => document.removeEventListener('keydown', onEscape);
  }, [fallbackFullscreen]);

  useEffect(() => {
    if (large) return;
    setFallbackFullscreen(false);
    if (document.fullscreenElement === cardRef.current) {
      void document.exitFullscreen().catch(() => undefined);
    }
  }, [large]);

  async function toggleFullscreen() {
    if (!large) {
      onSelect(camera.id);
      return;
    }
    if (fallbackFullscreen) {
      setFallbackFullscreen(false);
      return;
    }
    if (document.fullscreenElement === cardRef.current) {
      await document.exitFullscreen().catch(() => setFallbackFullscreen(false));
      return;
    }
    if (!cardRef.current?.requestFullscreen) {
      // iOS Safari does not support fullscreen on arbitrary HTML elements.
      setFallbackFullscreen(true);
      return;
    }
    try {
      await cardRef.current.requestFullscreen();
    } catch {
      setFallbackFullscreen(true);
    }
  }

  async function downloadSnapshot() {
    if (saving || !camera.online) return;
    setSaving(true);
    setSnapshotError('');
    try {
      const response = await fetch(`/api/cameras/${encodeURIComponent(camera.id)}/snapshot`, {
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(response.status === 404
          ? 'No hay una imagen reciente de esta cámara.'
          : 'No se pudo obtener la captura. Comprueba tu sesión y la conexión.');
      }
      const image = await response.blob();
      const url = URL.createObjectURL(image);
      const link = document.createElement('a');
      link.href = url;
      link.download = `maiavision-${camera.id}-${new Date().toISOString().replace(/[:.]/g, '-')}.jpg`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Allow the browser to finish the download before releasing the temporary blob.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (problem) {
      setSnapshotError(problem instanceof Error ? problem.message : 'No se pudo descargar la captura.');
    } finally {
      setSaving(false);
    }
  }

  return <article
    ref={cardRef}
    className={'camera-card ' + (large ? 'large ' : '') + (fallbackFullscreen ? 'fullscreen-fallback' : '')}
  >
    <div className="camera-header">
      <strong>{camera.name}</strong>
      <div className="camera-header-actions">
        <span className={'dot-label ' + (camera.online ? 'online' : '')}>
          {camera.online ? '● En directo' : '○ Sin señal'}
        </span>
        {large && <>
          <button type="button" className="camera-action" onClick={() => void downloadSnapshot()}
            disabled={!camera.online || saving} title="Descargar el último fotograma JPEG">
            {saving ? 'Guardando…' : '📸 Captura'}
          </button>
          <button type="button" className="camera-action" onClick={() => void toggleFullscreen()}
            aria-label={fullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}>
            {fullscreen ? '✕ Salir' : '⛶ Ampliar'}
          </button>
        </>}
      </div>
    </div>
    <div className="camera-screen">
      <button type="button" className="camera-screen-button"
        onClick={() => void toggleFullscreen()}
        aria-label={large
          ? (fullscreen ? `Salir de pantalla completa de ${camera.name}` : `Pantalla completa de ${camera.name}`)
          : `Abrir vista individual de ${camera.name}`}>
        {camera.online && !failed
          ? <img key={streamRevision} src={`/api/cameras/${encodeURIComponent(camera.id)}/stream?revision=${streamRevision}`}
              alt={`Vídeo en directo: ${camera.name}`} onError={() => setFailed(true)} />
          : <span className="offline"><span className="offline-icon">◉</span>
              <strong>{failed ? 'No se ha podido reproducir' : 'Cámara desconectada'}</strong>
              <small>Comprueba la conexión del agente</small></span>}
        <span className="camera-screen-hint" aria-hidden="true">
          {large ? (fullscreen ? 'Salir de pantalla completa' : '⛶ Pantalla completa') : '↗ Abrir cámara'}
        </span>
      </button>
    </div>
    {snapshotError && <p className="camera-snapshot-error" role="alert">{snapshotError}</p>}
    <footer>
      <span>{camera.online ? camera.status : 'Esperando señal'}</span>
      <small>{camera.seen_at ? new Date(camera.seen_at).toLocaleTimeString('es-ES') : 'Nunca conectada'}</small>
    </footer>
  </article>;
}
