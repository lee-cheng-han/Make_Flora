import React, { useRef, useState, useEffect } from 'react';
import ReactPlayer from 'react-player';

// Stream URL 
const STREAM_URL = import.meta.env.VITE_STREAM_URL || "http://localhost:5000/stream";
const DETECTION_API = STREAM_URL.replace(/\/stream\/?$/, "") + "/detection";

const App = () => {
  const [isExploring, setIsExploring] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const [analysis, setAnalysis] = useState({
    name: "Waiting...",
    language: "Bring a flower into view to hear its story.",
    poetic: "The silence of nature is waiting to be heard.",
    songUrl: "",
  });

  const streamRef = useRef(null);

  useEffect(() => {
    if (!isExploring) return;
    const poll = async () => {
      try {
        const res = await fetch(DETECTION_API);
        if (res.ok) {
          const data = await res.json();
          setAnalysis((prev) => ({
            ...prev,
            name: data.name ?? prev.name,
            language: data.language ?? prev.language,
            poetic: data.poetic ?? prev.poetic,
            songUrl: data.name && data.name !== "Waiting..." ? `https://www.youtube.com/results?search_query=${encodeURIComponent(data.name)}+ambient+music` : prev.songUrl,
          }));
          if (data.name && data.name !== "Waiting..." && data.name !== "object") {
            setIsPlaying(true);
          } else {
            setIsPlaying(false);
          }
        }
      } catch (e) {}
    };
    poll();
    const id = setInterval(poll, 500);
    return () => clearInterval(id);
  }, [isExploring]);

  const globalStyles = `
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .vinyl-spin {
      animation: spin 15s linear infinite;
    }
    .back-btn:hover {
      background: rgba(255, 255, 255, 0.9) !important;
      transform: translateX(-5px);
    }
  `;

  const LandingView = () => (
    <div style={styles.landingContainer}>
      <div style={styles.overlay}>
        <h1 style={styles.title}>Botanical Music</h1>
        <p style={styles.subtitle}>Hear the melody of every bloom</p>
        <button style={styles.startButton} onClick={() => setIsExploring(true)}>Start Exploring</button>
      </div>
    </div>
  );

  const CameraView = () => (
    <div style={styles.cameraViewContainer}>
      <style>{globalStyles}</style>
      <button 
        className="back-btn"
        onClick={() => setIsExploring(false)} 
        style={styles.minimalBackButton}
      >
        ← Back to Home
      </button>
      
      <div style={styles.mainGrid}>
        {/* 左侧：视频(上) + 花语(下) */}
        <div style={styles.leftColumn}>
          <div style={styles.videoContainer}>
            <div style={styles.mediaFrame}>
              <img 
                ref={streamRef}
                src={STREAM_URL} 
                alt="ESP32 Stream" 
                crossOrigin="anonymous" 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
              />
              <div style={styles.liveTag}>AI SCANNING...</div>
            </div>
          </div>

          <div style={styles.floriographyContainer}>
            <div style={styles.glassCard}>
              <h2 style={styles.infoTitle}>Floriography</h2>
              <div style={styles.scrollableContent}>
                <h3 style={styles.flowerName}>{analysis.name}</h3>
                <p style={styles.flowerLanguage}>{analysis.language}</p>
                <div style={styles.poeticBox}>
                  <p style={styles.poeticText}>"{analysis.poetic}"</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 右侧：完整唱片机 */}
        <div style={styles.rightColumn}>
          <div style={{...styles.glassCard, ...styles.recordPlayerLayout}}>
            <h2 style={styles.infoTitle}>Nature's Vinyl</h2>
            
            <div style={styles.recordWrapper}>
              <div style={{
                ...styles.vinylRecord,
                animationPlayState: isPlaying ? 'running' : 'paused'
              }} className="vinyl-spin">
                <div style={styles.vinylGrooves}></div>
                <div style={styles.vinylLabel}>
                  <div style={styles.vinylHole}></div>
                </div>
              </div>
              <div style={{
                ...styles.toneArm,
                transform: isPlaying ? 'rotate(20deg)' : 'rotate(-10deg)'
              }}></div>
            </div>

            <div style={styles.playerControls}>
              {analysis.songUrl && (
                <ReactPlayer 
                  url={analysis.songUrl} 
                  width="100%" 
                  height="45px" 
                  playing={isPlaying}
                  controls={true}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                />
              )}
            </div>
            <p style={styles.statusText}>
              {isPlaying ? `Playing harmonies for ${analysis.name}` : "Waiting for nature's signal..."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  return isExploring ? <CameraView /> : <LandingView />;
};

const theme = {
  bg: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2f1 100%)',
  glass: 'rgba(255, 255, 255, 0.7)',
  accent: '#26a69a',
  text: '#2d3436',
  lightText: '#636e72',
};

const styles = {
  landingContainer: { height: '100vh', width: '100vw', backgroundImage: 'url("/bg.jpg")', backgroundSize: 'cover', backgroundPosition: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center' },
  overlay: { backgroundColor: 'rgba(0, 0, 0, 0.35)', padding: '60px 80px', borderRadius: '24px', textAlign: 'center', color: 'white', backdropFilter: 'blur(10px)' },
  title: { fontFamily: '"Great Vibes", cursive', fontSize: '5.5rem', margin: '0' },
  subtitle: { fontFamily: '"Times New Roman", serif', fontSize: '1.2rem', margin: '10px 0 40px 0', letterSpacing: '2px', fontStyle: 'italic' },
  startButton: { padding: '12px 50px', fontSize: '1rem', border: '1px solid white', backgroundColor: 'transparent', color: 'white', borderRadius: '50px', cursor: 'pointer' },

  cameraViewContainer: { height: '100vh', width: '100vw', background: theme.bg, display: 'flex', overflow: 'hidden', boxSizing: 'border-box' },
  minimalBackButton: { 
    position: 'absolute', top: '25px', left: '25px', 
    backgroundColor: 'rgba(255, 255, 255, 0.5)', 
    padding: '10px 20px', borderRadius: '50px',
    border: '1px solid white', color: theme.text, 
    cursor: 'pointer', zIndex: 100,
    fontSize: '0.9rem', fontWeight: '600',
    transition: 'all 0.3s ease',
    boxShadow: '0 4px 15px rgba(0,0,0,0.05)'
  },
  
  mainGrid: { 
    flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', 
    padding: '80px 40px 40px 40px', gap: '30px', 
    maxHeight: '100vh', boxSizing: 'border-box' 
  },
  
  leftColumn: { display: 'flex', flexDirection: 'column', gap: '20px', height: '100%', overflow: 'hidden' },
  videoContainer: { height: '45%', position: 'relative', flexShrink: 0 },
  mediaFrame: { height: '100%', borderRadius: '24px', overflow: 'hidden', border: '6px solid white', boxShadow: '0 10px 30px rgba(0,0,0,0.1)' },
  liveTag: { position: 'absolute', top: '15px', right: '15px', backgroundColor: '#ff5252', color: 'white', padding: '3px 10px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 'bold' },
  
  floriographyContainer: { flex: 1, overflow: 'hidden' },
  glassCard: { 
    height: '100%', backgroundColor: theme.glass, backdropFilter: 'blur(10px)', 
    borderRadius: '24px', padding: '25px', border: '1px solid white', 
    boxShadow: '0 10px 30px rgba(0,0,0,0.05)', position: 'relative',
    display: 'flex', flexDirection: 'column', boxSizing: 'border-box'
  },
  scrollableContent: { flex: 1, overflowY: 'auto', paddingRight: '5px' },
  infoTitle: { fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '2px', color: theme.lightText, marginBottom: '15px', borderBottom: '1px solid rgba(0,0,0,0.05)', paddingBottom: '10px' },
  flowerName: { fontFamily: '"Great Vibes", cursive', fontSize: '3rem', color: theme.accent, margin: '0 0 10px 0' },
  flowerLanguage: { fontSize: '1.1rem', color: theme.text, lineHeight: '1.6', fontStyle: 'italic' },
  poeticBox: { marginTop: '20px', paddingLeft: '15px', borderLeft: `3px solid ${theme.accent}` },
  poeticText: { fontSize: '1.2rem', color: theme.lightText, fontStyle: 'italic' },
  aiLoading: { position: 'absolute', top: '25px', right: '25px', fontSize: '0.8rem', color: theme.accent, fontWeight: 'bold' },

  rightColumn: { display: 'flex', height: '100%', overflow: 'hidden' },
  recordPlayerLayout: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' },
  recordWrapper: { position: 'relative', width: 'min(350px, 80%)', aspectRatio: '1/1', margin: '20px 0' },
  vinylRecord: { width: '100%', height: '100%', borderRadius: '50%', backgroundColor: '#181818', position: 'relative', boxShadow: '0 15px 40px rgba(0,0,0,0.3)' },
  vinylGrooves: { position: 'absolute', top: '2%', left: '2%', right: '2%', bottom: '2%', borderRadius: '50%', background: 'repeating-radial-gradient(rgba(255,255,255,0.05) 0px, transparent 2px, rgba(255,255,255,0.05) 4px)' },
  vinylLabel: { position: 'absolute', top: '35%', left: '35%', width: '30%', height: '30%', borderRadius: '50%', backgroundColor: theme.accent, border: '4px solid #333' },
  vinylHole: { position: 'absolute', top: '45%', left: '45%', width: '10%', height: '10%', borderRadius: '50%', backgroundColor: '#181818' },
  toneArm: { position: 'absolute', top: '0', right: '-20px', width: 'min(150px, 40%)', height: '10px', backgroundColor: '#757575', borderRadius: '5px', transformOrigin: 'top right', transition: 'transform 1s cubic-bezier(0.4, 0, 0.2, 1)' },
  
  playerControls: { width: '80%', marginTop: '20px', flexShrink: 0 },
  statusText: { marginTop: '15px', fontSize: '0.9rem', color: theme.lightText, fontFamily: 'serif' }
};

export default App;
