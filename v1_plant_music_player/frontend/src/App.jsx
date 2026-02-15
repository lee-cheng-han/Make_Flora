import React, { useRef, useState, useCallback } from 'react';
import ReactPlayer from 'react-player';
import { GoogleGenerativeAI } from '@google/generative-ai';

// 1. 在这里填入你的 API KEY
const API_KEY = "AIzaSyAxFxa4XKoomll3GkPU2YrjqcRIkqx1zP8"; 
const genAI = new GoogleGenerativeAI(API_KEY);

// 你的 ESP32-CAM 视频流地址
const STREAM_URL = "http://172.19.129.149/stream";

const App = () => {
  const [isExploring, setIsExploring] = useState(false);
  const [capturedImage, setCapturedImage] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // 识别结果状态
  const [analysis, setAnalysis] = useState({
    name: "Waiting...",
    language: "Capture a flower to see its mystery.",
    poetic: "The silence of nature is waiting to be heard.",
    songUrl: "",
  });

  // 用于引用流媒体图片
  const streamRef = useRef(null);

  // 核心功能：调用 Gemini API 识别植物
  const identifyPlant = async (base64Image) => {
    setLoading(true);
    try {
      const base64Data = base64Image.split(',')[1];
      const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

      const prompt = `
        Identify the flower or plant in this image. 
        Return the result strictly in JSON format with the following keys:
        - "name": The common name of the flower.
        - "language": A deep and meaningful floriography (flower language) description.
        - "poetic": 2-3 poetic, beautiful English phrases or sentences that evoke the mood of this flower.
        - "music_mood": A specific mood or genre for music (e.g., "Melancholic Piano", "Lively Jazz").
      `;

      const imagePart = {
        inlineData: { data: base64Data, mimeType: "image/jpeg" },
      };

      const result = await model.generateContent([prompt, imagePart]);
      const response = await result.response;
      const text = response.text();
      
      const jsonMatch = text.match(/\{.*\}/s);
      const data = JSON.parse(jsonMatch[0]);

      setAnalysis({
        name: data.name,
        language: data.language,
        poetic: data.poetic,
        songUrl: `https://www.youtube.com/results?search_query=${data.name}+ambient+music` 
      });

    } catch (error) {
      console.error("Gemini Error:", error);
      setAnalysis(prev => ({ ...prev, name: "Recognition Failed", language: "Please try again." }));
    } finally {
      setLoading(false);
    }
  };

  // 从视频流 <img> 标签抓取当前帧并拍照
  const capture = useCallback(() => {
    const img = streamRef.current;
    if (!img) return;

    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    
    try {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const imageSrc = canvas.toDataURL('image/jpeg');
      setCapturedImage(imageSrc);
      identifyPlant(imageSrc); // 拍照后立即识别
    } catch (e) {
      console.error("Capture Error (Maybe CORS issue):", e);
      alert("无法抓取视频流，请检查跨域设置或 ESP32 连接");
    }
  }, [streamRef]);

  const reset = () => {
    setCapturedImage(null);
    setAnalysis({
      name: "Waiting...",
      language: "Capture a flower to see its mystery.",
      poetic: "The silence of nature is waiting to be heard.",
      songUrl: "",
    });
  };

  // --- 视图组件 ---
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
      <button onClick={() => setIsExploring(false)} style={styles.minimalBackButton}>Back to Home</button>
      <div style={styles.mainLayout}>
        {/* 左侧：ESP32-CAM 视频流 */}
        <div style={styles.leftPanel}>
          <div style={styles.mediaFrame}>
            {!capturedImage ? (
              <img 
                ref={streamRef}
                src={STREAM_URL} 
                alt="ESP32 Stream" 
                crossOrigin="anonymous" // 允许跨域抓取画面
                style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
              />
            ) : (
              <img src={capturedImage} alt="Captured" style={styles.capturedImage} />
            )}
            {loading && <div style={styles.loadingOverlay}>Analyzing the Soul of the Bloom...</div>}
          </div>
          <div style={styles.cameraControls}>
            {!capturedImage ? (
              <button onClick={capture} style={styles.captureBtn}>Take Photo</button>
            ) : (
              <button onClick={reset} style={styles.resetBtn}>Reset</button>
            )}
          </div>
        </div>

        {/* 右侧：分析 */}
        <div style={styles.rightPanel}>
          <div style={styles.infoSection}>
            <h2 style={styles.infoTitle}>Floriography</h2>
            <div style={styles.infoContent}>
              <h3 style={styles.flowerName}>{analysis.name}</h3>
              <p style={styles.flowerLanguage}>{analysis.language}</p>
              <div style={styles.poeticBox}>
                <p style={styles.poeticText}>"{analysis.poetic}"</p>
              </div>
            </div>
          </div>

          <div style={styles.audioSection}>
            <h2 style={styles.infoTitle}>Melody</h2>
            <div style={styles.playerWrapper}>
              {analysis.songUrl && (
                <ReactPlayer url={analysis.songUrl} width="100%" height="50px" playing={!!capturedImage && !loading} controls={true} />
              )}
              <p style={styles.audioHint}>
                {loading ? "Searching for the right melody..." : capturedImage ? "Harmony Found" : "Capture to begin"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return isExploring ? <CameraView /> : <LandingView />;
};

// --- 样式对象 ---
const styles = {
  landingContainer: { height: '100vh', width: '100vw', backgroundImage: 'url("/bg.jpg")', backgroundSize: 'cover', backgroundPosition: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center' },
  overlay: { backgroundColor: 'rgba(0, 0, 0, 0.35)', padding: '60px 80px', borderRadius: '24px', textAlign: 'center', color: 'white', backdropFilter: 'blur(10px)', border: '1px solid rgba(255, 255, 255, 0.2)' },
  title: { fontFamily: '"Great Vibes", cursive', fontSize: '5.5rem', margin: '0' },
  subtitle: { fontFamily: '"Times New Roman", serif', fontSize: '1.2rem', margin: '10px 0 40px 0', letterSpacing: '2px', fontStyle: 'italic' },
  startButton: { padding: '12px 50px', fontSize: '1rem', fontFamily: 'serif', backgroundColor: 'transparent', color: 'white', border: '1px solid white', borderRadius: '50px', cursor: 'pointer' },
  cameraViewContainer: { height: '100vh', width: '100vw', backgroundColor: '#0f141a', color: 'white', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  minimalBackButton: { position: 'absolute', top: '20px', left: '20px', background: 'none', border: 'none', color: '#888', cursor: 'pointer', textDecoration: 'underline', zIndex: 10 },
  mainLayout: { flex: 1, display: 'flex', padding: '60px 40px 40px 40px', gap: '40px' },
  leftPanel: { flex: 1.2, display: 'flex', flexDirection: 'column', gap: '20px' },
  mediaFrame: { flex: 1, borderRadius: '20px', overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.4)', border: '1px solid #333', backgroundColor: '#000', position: 'relative' },
  capturedImage: { width: '100%', height: '100%', objectFit: 'cover' },
  loadingOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', justifyContent: 'center', alignItems: 'center', fontSize: '1.2rem', color: '#a5c9e5', fontFamily: 'serif', fontStyle: 'italic' },
  cameraControls: { display: 'flex', justifyContent: 'center', padding: '10px' },
  captureBtn: { padding: '15px 60px', borderRadius: '50px', border: 'none', backgroundColor: '#fff', color: '#000', fontWeight: 'bold', cursor: 'pointer', fontSize: '1rem' },
  resetBtn: { padding: '15px 60px', borderRadius: '50px', border: '1px solid #fff', backgroundColor: 'transparent', color: '#fff', cursor: 'pointer', fontSize: '1rem' },
  rightPanel: { flex: 0.8, display: 'flex', flexDirection: 'column', gap: '30px' },
  infoSection: { flex: 1, backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '20px', padding: '30px', border: '1px solid rgba(255,255,255,0.1)', overflowY: 'auto' },
  audioSection: { height: '200px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '20px', padding: '30px', border: '1px solid rgba(255,255,255,0.1)' },
  infoTitle: { fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#666', marginBottom: '20px', borderBottom: '1px solid #333', paddingBottom: '10px' },
  flowerName: { fontFamily: '"Great Vibes", cursive', fontSize: '3rem', color: '#a5c9e5', margin: '0 0 10px 0' },
  flowerLanguage: { fontFamily: 'serif', fontSize: '1.1rem', lineHeight: '1.6', color: '#ccc', fontStyle: 'italic' },
  poeticBox: { marginTop: '25px', paddingLeft: '20px', borderLeft: '2px solid #a5c9e5' },
  poeticText: { fontFamily: 'serif', fontSize: '1.2rem', color: '#e0e0e0', lineHeight: '1.4', fontStyle: 'italic' },
  playerWrapper: { marginTop: '10px' },
  audioHint: { textAlign: 'center', fontSize: '0.8rem', color: '#555', marginTop: '10px' }
};

export default App;