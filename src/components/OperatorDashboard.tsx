import React, { useState, useEffect, useRef } from 'react';
import { analyzeImageForDefects } from '../utils/cameraProcessing';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  AlertTriangle,
  AlertOctagon,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Camera,
  Upload,
  Download,
  Sliders,
  Gauge,
  Activity,
  FileText,
  Check,
  X,
  Search,
  Eye,
  RefreshCw,
  Zap,
  Crosshair,
  TrendingUp,
  Radio,
  Bell,
  Clock,
  ArrowRight,
  ChevronRight,
  Info,
  Lock,
  Cpu,
  Layers,
  Database
} from 'lucide-react';

export interface InspectionRecord {
  inspection_id: string;
  product_id: string;
  timestamp: string;
  defect_detected: boolean;
  defect_type: string;
  severity: 'Low' | 'Medium' | 'High' | 'Critical' | 'Indeterminate';
  confidence: number;
  location: string;
  decision: 'ACCEPT' | 'REJECT' | 'MANUAL_REVIEW' | 'CONDITIONAL_FLAG';
  recommendation: string;
  inference_ms?: number;
  boxes?: Array<{
    class_name: string;
    confidence: number;
    xmin: number;
    ymin: number;
    xmax: number;
    ymax: number;
    area_ratio?: number;
    severity?: string;
  }>;
  root_cause?: string;
  implications?: string;
  remediation_steps?: string[];
  shift_log_summary?: string;
  operator_logs?: Array<{
    operator_id: string;
    action: string;
    notes: string;
    timestamp: string;
  }>;
}

interface OperatorDashboardProps {
  initialHistory: InspectionRecord[];
  onAddInspection: (record: InspectionRecord) => void;
  onOverrideInspection: (inspectionId: string, action: string, operatorId: string, notes: string) => void;
  onNavigateToTab?: (tab: string) => void;
}

// Built-in steel strip defect presets for live simulation
const CONVEYOR_SPECIMENS = [
  {
    type: 'crazing',
    name: 'Crazing',
    severity: 'Critical' as const,
    confidence: 0.962,
    location: 'Upper-right surface region',
    decision: 'REJECT' as const,
    box: { xmin: 130, ymin: 40, xmax: 270, ymax: 180 },
    recommendation: 'Immediate reject. Severe micro-crack network detected. Quench nozzle thermal shock.',
    root_cause: 'Steep cooling temperature gradient during secondary spray cooling stage.',
    implications: 'Micro-cracks act as severe stress-raisers leading to catastrophic brittle fracture.',
    remediation_steps: [
      'Stop cold-rolling feed into slitter #2',
      'Inspect spray nozzle bar #4 for blocked descaling orifices',
      'Quarantine coil batch for ultrasonic testing'
    ]
  },
  {
    type: 'inclusion',
    name: 'Inclusion',
    severity: 'High' as const,
    confidence: 0.941,
    location: 'Central longitudinal band',
    decision: 'REJECT' as const,
    box: { xmin: 80, ymin: 80, xmax: 190, ymax: 190 },
    recommendation: 'Reject strip segment. Non-metallic slag oxide particle trapped in matrix.',
    root_cause: 'Ladle slag carry-over during continuous casting tundish transition.',
    implications: 'Causes severe sheet delamination and stamping splits under deep drawing.',
    remediation_steps: [
      'Flag coil for scrap or non-critical downgrading',
      'Verify slag detection electromagnetic sensor on tundish',
      'Alert melt-shop quality supervisor'
    ]
  },
  {
    type: 'scratches',
    name: 'Scratches',
    severity: 'Medium' as const,
    confidence: 0.895,
    location: 'Lower edge zone (strip border)',
    decision: 'CONDITIONAL_FLAG' as const,
    box: { xmin: 160, ymin: 130, xmax: 300, ymax: 180 },
    recommendation: 'Conditional flag. Mechanical guide rail friction scratch. Verify groove depth.',
    root_cause: 'Debris buildup on guide horn or unlubricated accumulator pinch rolls.',
    implications: 'May breach electro-galvanized coating and initiate premature red rust.',
    remediation_steps: [
      'Perform contact stylus profilometry (check depth < 0.05 mm limit)',
      'Clean accumulator entry guide pads',
      'Replenish synthetic roll lubricant'
    ]
  },
  {
    type: 'pitted_surface',
    name: 'Pitted Surface',
    severity: 'High' as const,
    confidence: 0.918,
    location: 'Mid-left rolling quadrant',
    decision: 'REJECT' as const,
    box: { xmin: 30, ymin: 70, xmax: 150, ymax: 170 },
    recommendation: 'Reject. Deep acid pickling pits or work-roll spall marks.',
    root_cause: 'Acid bath over-pickling or roll barrel surface fatigue spalling.',
    implications: 'Reduces nominal gauge thickness; creates galvanic corrosion initiation sites.',
    remediation_steps: [
      'Verify pickling line HCl acid concentration and line speed',
      'Schedule work roll barrel change on Mill Stand #3',
      'Measure residual sheet thickness across strip'
    ]
  },
  {
    type: 'rolled_in_scale',
    name: 'Rolled-in Scale',
    severity: 'High' as const,
    confidence: 0.934,
    location: 'Transverse trailing edge',
    decision: 'REJECT' as const,
    box: { xmin: 70, ymin: 30, xmax: 220, ymax: 110 },
    recommendation: 'Reject. Embedded iron oxide mill scale pressed into strip surface.',
    root_cause: 'Hydraulic descaling water header low pressure (<160 bar) during roughing pass.',
    implications: 'Scale breaks away during downstream stamping leaving deep cavities.',
    remediation_steps: [
      'Verify descaling water pump pressure delivery',
      'Inspect descaler nozzle headers for scale clogging',
      'Adjust strip entry furnace atmospheric oxygen ratio'
    ]
  },
  {
    type: 'normal',
    name: 'Defect-Free (Normal)',
    severity: 'Low' as const,
    confidence: 0.988,
    location: 'Uniform full-field strip',
    decision: 'ACCEPT' as const,
    box: { xmin: 0, ymin: 0, xmax: 0, ymax: 0 },
    recommendation: 'ACCEPT. Clean cold-rolled surface conforming to ASTM A1008 Grade 1.',
    root_cause: 'Normal steady-state cold-rolling operation.',
    implications: 'Optimal surface fatigue life and uniform zinc coating adhesion.',
    remediation_steps: [
      'Release strip segment to continuous tension leveler',
      'Log acceptance in SQLite inspection database',
      'Proceed with automated coil winding'
    ]
  },
  {
    type: 'uncertain_pit',
    name: 'Pitted Surface (Low Confidence)',
    severity: 'Indeterminate' as const,
    confidence: 0.618,
    location: 'Edge border margin',
    decision: 'MANUAL_REVIEW' as const,
    box: { xmin: 20, ymin: 30, xmax: 110, ymax: 100 },
    recommendation: 'AUTOMATED REJECT BLOCKED. Confidence 61.8% is below 65% gate threshold. Operator manual review required.',
    root_cause: 'Ambiguous surface texture or optical specular reflection glare.',
    implications: 'Risk of false-positive scrap or undetected micro-pit leakage.',
    remediation_steps: [
      'Operator optical loupe inspection at station',
      'Confirm whether texture is harmless oil residue or true pit',
      'Submit signed operator override decision'
    ]
  }
];

export const OperatorDashboard: React.FC<OperatorDashboardProps> = ({
  initialHistory,
  onAddInspection,
  onOverrideInspection,
  onNavigateToTab
}) => {
  // Operational Line State
  const [lineStatus, setLineStatus] = useState<'RUNNING' | 'PAUSED' | 'E-STOP'>('RUNNING');
  const [lineSpeed, setLineSpeed] = useState<number>(2.4); // m/s
  const [activeCoilId, setActiveCoilId] = useState<string>('COIL-2026-X892');
  const [operatorId, setOperatorId] = useState<string>('OP-4482');
  const [audioAlarmEnabled, setAudioAlarmEnabled] = useState<boolean>(true);
  const [autoInspectInterval, setAutoInspectInterval] = useState<boolean>(false);
  const [specimenCursor, setSpecimenCursor] = useState<number>(0);

  // Active Screen / Viewport State
  const [activeRecord, setActiveRecord] = useState<InspectionRecord>(
    initialHistory[0] || {
      inspection_id: 'INS-2026-001',
      product_id: 'STEEL-CR-104',
      timestamp: new Date().toISOString(),
      defect_detected: true,
      defect_type: 'crazing',
      severity: 'Critical',
      confidence: 0.942,
      location: 'Upper-right surface region',
      decision: 'REJECT',
      recommendation: 'Quarantine coil segment immediately. Critical crazing micro-cracks detected.',
      inference_ms: 38.4,
      boxes: [{ class_name: 'crazing', confidence: 0.942, xmin: 80, ymin: 45, xmax: 240, ymax: 190, area_ratio: 0.082, severity: 'Critical' }],
      root_cause: 'Thermal shock and steep cooling temperature gradients during continuous casting.',
      implications: 'Micro-crack network poses severe brittle fracture risk during cold stamping.',
      remediation_steps: ['Halt line feed', 'Calibrate quench nozzles', 'Notify melt-shop'],
      shift_log_summary: 'CRITICAL REJECT: Thermal crazing detected in upper-right quadrant. Auto-quarantine.'
    }
  );

  const [activeHistory, setActiveHistory] = useState<InspectionRecord[]>(initialHistory);
  const [isFrozen, setIsFrozen] = useState<boolean>(false);
  const [selectedOverlayView, setSelectedOverlayView] = useState<'boxes' | 'heatmap' | 'raw'>('boxes');
  const [notificationToast, setNotificationToast] = useState<{ title: string; message: string; type: 'critical' | 'warn' | 'success' } | null>(null);

  // Manual Override Modal
  const [overrideModalOpen, setOverrideModalOpen] = useState<boolean>(false);
  const [overrideTargetRecord, setOverrideTargetRecord] = useState<InspectionRecord | null>(null);
  const [overrideActionType, setOverrideActionType] = useState<'OVERRIDE_ACCEPT' | 'OVERRIDE_REJECT' | 'VERIFIED'>('OVERRIDE_ACCEPT');
  const [overrideBadgeInput, setOverrideBadgeInput] = useState<string>('OP-4482');
  const [overrideReasonCode, setOverrideReasonCode] = useState<string>('SURFACE_PROFILOMETRY_PASS');
  const [overrideNotesInput, setOverrideNotesInput] = useState<string>('Physical dial depth micrometer confirms scratch depth is 0.021mm (<0.05mm threshold). Safe for structural automotive skin.');

  // Certificate / Report Modal
  const [certificateModalOpen, setCertificateModalOpen] = useState<boolean>(false);
  const [certificateRecord, setCertificateRecord] = useState<InspectionRecord | null>(null);

  // Canvas Ref for Conveyor Simulation
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const conveyorOffsetRef = useRef<number>(0);

  // Live Stream & Specimen Upload States
  const [streamSource, setStreamSource] = useState<'conveyor' | 'webcam' | 'upload'>('conveyor');
  const [webcamStreaming, setWebcamStreaming] = useState<boolean>(false);
  const [webcamError, setWebcamError] = useState<string | null>(null);
  const [uploadedImage, setUploadedImage] = useState<HTMLImageElement | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isProcessingInspection, setIsProcessingInspection] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleStartWebcam = async () => {
    setWebcamError(null);
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('MediaDevices API not supported in this browser environment.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' }
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play().catch(console.error);
        };
      }
      setWebcamStreaming(true);
      setStreamSource('webcam');
    } catch (err: any) {
      console.error('Webcam access error:', err);
      let msg = err.message || 'Unable to access web camera.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Camera permission was denied. Please allow camera access in browser permissions.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No camera device found. Please connect a USB camera.';
      }
      setWebcamError(msg);
      setWebcamStreaming(false);
    }
  };

  const handleStopWebcam = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setWebcamStreaming(false);
  };

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        setUploadedImage(img);
        setUploadedFileName(file.name);
        setStreamSource('upload');
      };
      img.src = event.target?.result as string;
    };
    reader.readAsDataURL(file);
  };

  const handleInspectLiveCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setIsProcessingInspection(true);
    try {
      const detection = analyzeImageForDefects(canvas);
      const now = new Date();
      const hasDefect = detection.hasDefect;
      const defectType = detection.defectType;
      const decision = hasDefect
        ? (detection.severity === 'Critical' ? 'REJECT' : detection.severity === 'High' ? 'REJECT' : 'MANUAL_REVIEW')
        : 'ACCEPT';
      const loc = detection.box.xc < 0.35 ? 'Drive Side (DS)' : detection.box.xc > 0.65 ? 'Operator Side (OS)' : 'Central Web';

      const newRecord: InspectionRecord = {
        inspection_id: `INS-2026-${String(activeHistory.length + 1).padStart(3, '0')}`,
        product_id: streamSource === 'upload' && uploadedFileName
          ? `UPLOAD-${uploadedFileName.replace(/\.[^/.]+$/, '').toUpperCase().slice(0, 8)}`
          : `CAM-${now.getHours()}${now.getMinutes()}${now.getSeconds()}`,
        timestamp: now.toISOString(),
        defect_detected: hasDefect,
        defect_type: defectType,
        severity: detection.severity,
        confidence: detection.confidence,
        location: loc,
        decision: decision,
        recommendation: detection.recommendation,
        inference_ms: +(28 + Math.random() * 8).toFixed(1),
        boxes: hasDefect
          ? [
              {
                class_name: defectType,
                confidence: detection.confidence,
                xmin: Math.round((detection.box.xmin * 300) / canvas.width),
                ymin: Math.round((detection.box.ymin * 200) / canvas.height),
                xmax: Math.round((detection.box.xmax * 300) / canvas.width),
                ymax: Math.round((detection.box.ymax * 200) / canvas.height),
                area_ratio: detection.box.areaRatio,
                severity: detection.severity
              }
            ]
          : [],
        root_cause: detection.rootCause,
        implications: detection.implications,
        remediation_steps: detection.remediationSteps,
        shift_log_summary: `${decision}: ${defectType.toUpperCase()} (${(detection.confidence * 100).toFixed(1)}%) in ${loc}`
      };
      setActiveRecord(newRecord);
      setActiveHistory((prev) => [newRecord, ...prev]);
      onAddInspection(newRecord);
      if (detection.severity === 'Critical' || detection.severity === 'High') {
        playBuzzer('critical');
      }
    } catch (err) {
      console.error('Inspection error:', err);
    } finally {
      setIsProcessingInspection(false);
    }
  };

  // Audio Buzzer Synthesizer
  const playBuzzer = (type: 'critical' | 'alert' | 'estop') => {
    if (!audioAlarmEnabled) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'estop') {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(180, ctx.currentTime + 0.45);
        gain.gain.setValueAtTime(0.25, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.45);
        osc.start();
        osc.stop(ctx.currentTime + 0.5);
      } else if (type === 'critical') {
        osc.type = 'square';
        osc.frequency.setValueAtTime(780, ctx.currentTime);
        osc.frequency.setValueAtTime(620, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.18, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      } else {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(520, ctx.currentTime);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
        osc.start();
        osc.stop(ctx.currentTime + 0.2);
      }
    } catch {
      // AudioContext blocked before interaction
    }
  };

  // Sync initialHistory if parent changes
  useEffect(() => {
    setActiveHistory(initialHistory);
    if (initialHistory.length > 0 && !activeRecord) {
      setActiveRecord(initialHistory[0]);
    }
  }, [initialHistory]);

  // Conveyor Canvas Drawing Animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let isRunning = true;

    const render = () => {
      if (!isRunning) return;

      const width = canvas.width;
      const height = canvas.height;

      // Clear Canvas
      ctx.fillStyle = '#0f172a'; // slate-900
      ctx.fillRect(0, 0, width, height);

      // Advance conveyor if running
      if (lineStatus === 'RUNNING' && !isFrozen) {
        conveyorOffsetRef.current = (conveyorOffsetRef.current + lineSpeed * 1.8) % 60;
      }

      if (streamSource === 'webcam' && webcamStreaming && videoRef.current && videoRef.current.readyState >= 2) {
        // Draw live webcam video stream onto the inspection strip
        ctx.drawImage(videoRef.current, 20, 20, width - 40, height - 40);
      } else if (streamSource === 'upload' && uploadedImage) {
        // Draw uploaded specimen photo onto the inspection strip
        ctx.drawImage(uploadedImage, 20, 20, width - 40, height - 40);
      } else {
        // Draw Steel Strip Texture (brushed steel appearance)
        const grad = ctx.createLinearGradient(0, 0, width, 0);
        grad.addColorStop(0, '#1e293b');
        grad.addColorStop(0.1, '#334155');
        grad.addColorStop(0.5, '#475569');
        grad.addColorStop(0.9, '#334155');
        grad.addColorStop(1, '#1e293b');

        ctx.fillStyle = grad;
        ctx.fillRect(20, 20, width - 40, height - 40);

        // Draw rolling grains (horizontal longitudinal striations)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        for (let y = 30; y < height - 30; y += 8) {
          ctx.beginPath();
          ctx.moveTo(20, y);
          ctx.lineTo(width - 20, y);
          ctx.stroke();
        }

        // Draw moving conveyor rollers / seam pulses
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
        ctx.lineWidth = 2;
        for (let x = (conveyorOffsetRef.current % 60); x < width - 40; x += 60) {
          ctx.beginPath();
          ctx.moveTo(x + 20, 20);
          ctx.lineTo(x + 20, height - 20);
          ctx.stroke();
        }
      }

      // Millimeter Scale Rulers (Top & Left)
      ctx.fillStyle = '#0284c7'; // cyan
      ctx.font = '9px monospace';
      for (let mm = 0; mm <= 200; mm += 20) {
        const xPos = 20 + (mm / 200) * (width - 40);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
        ctx.beginPath();
        ctx.moveTo(xPos, 14);
        ctx.lineTo(xPos, 20);
        ctx.stroke();
        ctx.fillText(`${mm}mm`, xPos - 8, 12);
      }

      // Draw active defect visualization on the strip
      if (activeRecord.defect_detected && activeRecord.boxes && activeRecord.boxes.length > 0) {
        const box = activeRecord.boxes[0];
        // Scale box from 300x200 normalized space to canvas space
        const scaleX = (width - 40) / 300;
        const scaleY = (height - 40) / 200;
        const bx = 20 + box.xmin * scaleX;
        const by = 20 + box.ymin * scaleY;
        const bw = Math.max(30, (box.xmax - box.xmin) * scaleX);
        const bh = Math.max(30, (box.ymax - box.ymin) * scaleY);

        if (selectedOverlayView === 'boxes' || selectedOverlayView === 'heatmap') {
          // Defect texture simulation
          if (activeRecord.defect_type === 'crazing') {
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.85)'; // red cracks
            ctx.lineWidth = 1.5;
            for (let i = 0; i < 7; i++) {
              ctx.beginPath();
              ctx.moveTo(bx + Math.random() * bw, by + Math.random() * bh);
              ctx.lineTo(bx + Math.random() * bw, by + Math.random() * bh);
              ctx.stroke();
            }
          } else if (activeRecord.defect_type === 'inclusion') {
            ctx.fillStyle = 'rgba(30, 41, 59, 0.95)'; // dark slag chunk
            ctx.beginPath();
            ctx.ellipse(bx + bw / 2, by + bh / 2, bw / 3, bh / 3, Math.PI / 4, 0, 2 * Math.PI);
            ctx.fill();
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
            ctx.stroke();
          } else if (activeRecord.defect_type === 'scratches') {
            ctx.strokeStyle = 'rgba(245, 158, 11, 0.9)'; // amber line
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(bx, by + bh / 2);
            ctx.lineTo(bx + bw, by + bh / 2);
            ctx.stroke();
          } else if (activeRecord.defect_type === 'pitted_surface') {
            ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
            for (let p = 0; p < 8; p++) {
              ctx.beginPath();
              ctx.arc(bx + (p * bw) / 9 + 5, by + ((p % 3) * bh) / 4 + 8, 3.5, 0, 2 * Math.PI);
              ctx.fill();
            }
          }

          if (selectedOverlayView === 'boxes') {
            // High-contrast bounding box
            const boxColor =
              activeRecord.severity === 'Critical'
                ? '#ef4444' // red
                : activeRecord.severity === 'High'
                ? '#f97316' // orange
                : activeRecord.severity === 'Medium'
                ? '#f59e0b' // amber
                : '#3b82f6'; // blue (indeterminate)

            ctx.strokeStyle = boxColor;
            ctx.lineWidth = 2.5;
            ctx.setLineDash([6, 3]);
            ctx.strokeRect(bx, by, bw, bh);
            ctx.setLineDash([]);

            // Corner reticles
            const reticleLen = 10;
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            // Top-left
            ctx.beginPath();
            ctx.moveTo(bx, by + reticleLen);
            ctx.lineTo(bx, by);
            ctx.lineTo(bx + reticleLen, by);
            ctx.stroke();
            // Bottom-right
            ctx.beginPath();
            ctx.moveTo(bx + bw, by + bh - reticleLen);
            ctx.lineTo(bx + bw, by + bh);
            ctx.lineTo(bx + bw - reticleLen, by + bh);
            ctx.stroke();

            // Label tag above box
            ctx.fillStyle = boxColor;
            ctx.fillRect(bx, Math.max(22, by - 18), 140, 16);
            ctx.fillStyle = '#000000';
            ctx.font = 'bold 10px monospace';
            ctx.fillText(
              `${activeRecord.defect_type.toUpperCase()} ${(activeRecord.confidence * 100).toFixed(1)}%`,
              bx + 4,
              Math.max(34, by - 6)
            );
          } else if (selectedOverlayView === 'heatmap') {
            // Anomaly Thermal Gradient
            const hGrad = ctx.createRadialGradient(bx + bw / 2, by + bh / 2, 5, bx + bw / 2, by + bh / 2, bw);
            hGrad.addColorStop(0, 'rgba(239, 68, 68, 0.7)');
            hGrad.addColorStop(0.5, 'rgba(245, 158, 11, 0.4)');
            hGrad.addColorStop(1, 'rgba(59, 130, 246, 0)');
            ctx.fillStyle = hGrad;
            ctx.fillRect(bx - 20, by - 20, bw + 40, bh + 40);
          }
        }
      }

      // Draw Center Optical Inspection Reticle
      ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)'; // emerald reticle
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(width / 2, 20);
      ctx.lineTo(width / 2, height - 20);
      ctx.moveTo(20, height / 2);
      ctx.lineTo(width - 20, height / 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Status indicator on top corner of feed
      ctx.fillStyle = lineStatus === 'RUNNING' ? 'rgba(16, 185, 129, 0.9)' : lineStatus === 'PAUSED' ? 'rgba(245, 158, 11, 0.9)' : 'rgba(239, 68, 68, 0.9)';
      ctx.beginPath();
      ctx.arc(36, 36, 5, 0, 2 * Math.PI);
      ctx.fill();

      ctx.fillStyle = '#f8fafc';
      ctx.font = '10px monospace';
      const streamLabel =
        streamSource === 'webcam' && webcamStreaming
          ? `CAM-LIVE [Webcam Stream 720p@30FPS] | ${lineStatus}`
          : streamSource === 'upload' && uploadedFileName
          ? `SPECIMEN [${uploadedFileName}] | Static Frame`
          : `CAM-01 [V4L2 1280x720@30FPS] | ${lineStatus} | SPD: ${lineSpeed.toFixed(1)} m/s`;
      ctx.fillText(streamLabel, 48, 39);

      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      isRunning = false;
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [lineStatus, lineSpeed, isFrozen, activeRecord, selectedOverlayView, streamSource, webcamStreaming, uploadedImage, uploadedFileName]);

  // Automated specimen injection loop (when auto-feed toggled)
  useEffect(() => {
    if (!autoInspectInterval || lineStatus !== 'RUNNING') return;
    const interval = setInterval(() => {
      handleInspectNextPreset();
    }, 4000);
    return () => clearInterval(interval);
  }, [autoInspectInterval, lineStatus, specimenCursor]);

  // Handle triggering next sample inspection
  const handleInspectNextPreset = () => {
    const nextIdx = (specimenCursor + 1) % CONVEYOR_SPECIMENS.length;
    setSpecimenCursor(nextIdx);
    const specimen = CONVEYOR_SPECIMENS[nextIdx];

    const now = new Date();
    const newId = `INS-2026-${String(activeHistory.length + 1).padStart(3, '0')}`;
    const productSerial = `STEEL-${specimen.type.substring(0, 2).toUpperCase()}-${Math.floor(100 + Math.random() * 900)}`;

    const newRecord: InspectionRecord = {
      inspection_id: newId,
      product_id: productSerial,
      timestamp: now.toISOString(),
      defect_detected: specimen.type !== 'normal',
      defect_type: specimen.type,
      severity: specimen.severity,
      confidence: specimen.confidence,
      location: specimen.location,
      decision: specimen.decision,
      recommendation: specimen.recommendation,
      inference_ms: +(32 + Math.random() * 8).toFixed(1),
      boxes:
        specimen.type !== 'normal'
          ? [
              {
                class_name: specimen.type,
                confidence: specimen.confidence,
                xmin: specimen.box.xmin,
                ymin: specimen.box.ymin,
                xmax: specimen.box.xmax,
                ymax: specimen.box.ymax,
                area_ratio: +(((specimen.box.xmax - specimen.box.xmin) * (specimen.box.ymax - specimen.box.ymin)) / 60000).toFixed(3),
                severity: specimen.severity
              }
            ]
          : [],
      root_cause: specimen.root_cause,
      implications: specimen.implications,
      remediation_steps: specimen.remediation_steps,
      shift_log_summary: `${specimen.decision}: ${specimen.type.toUpperCase()} - ${specimen.location}. Telemetry logged.`
    };

    setActiveRecord(newRecord);
    setActiveHistory((prev) => [newRecord, ...prev]);
    onAddInspection(newRecord);

    // Audio alarm trigger
    if (specimen.severity === 'Critical' || specimen.severity === 'High') {
      playBuzzer('critical');
      setNotificationToast({
        title: `DEFECT DETECTED: ${specimen.name.toUpperCase()}`,
        message: `${specimen.severity} Severity in ${specimen.location}. Action: ${specimen.decision}`,
        type: 'critical'
      });
    } else if (specimen.decision === 'MANUAL_REVIEW') {
      playBuzzer('alert');
      setNotificationToast({
        title: 'MANUAL REVIEW REQUIRED',
        message: `Confidence ${+(specimen.confidence * 100).toFixed(1)}% < 65% gate cutoff. Automated reject held.`,
        type: 'warn'
      });
    } else {
      setNotificationToast({
        title: 'SPECIMEN ACCEPTED',
        message: `${productSerial} verified defect-free cold-rolled surface.`,
        type: 'success'
      });
    }
  };

  // Emergency Stop Handler
  const handleEmergencyStop = () => {
    setLineStatus('E-STOP');
    playBuzzer('estop');
    const safetyRecord: InspectionRecord = {
      inspection_id: `SAFETY-ESTOP-${Date.now()}`,
      product_id: activeCoilId,
      timestamp: new Date().toISOString(),
      defect_detected: true,
      defect_type: 'EMERGENCY_STOP',
      severity: 'Critical',
      confidence: 1.0,
      location: 'Main Rolling Line Conveyor Feed',
      decision: 'REJECT',
      recommendation: 'EMERGENCY STOP ENGAGED BY OPERATOR. Mechanical line interlocking trip active.',
      inference_ms: 0.1,
      operator_logs: [
        {
          operator_id: operatorId,
          action: 'E-STOP_TRIGGERED',
          notes: 'Immediate conveyor trip activated by operator at HMI dashboard.',
          timestamp: new Date().toISOString()
        }
      ]
    };
    setActiveHistory((prev) => [safetyRecord, ...prev]);
    onAddInspection(safetyRecord);
    setNotificationToast({
      title: 'EMERGENCY STOP (E-STOP) ENGAGED',
      message: 'Rolling line halted. Physical drive contactor interlock open.',
      type: 'critical'
    });
  };

  // Operator Action (Accept / Flag / Reject override)
  const handleOperatorAction = (action: 'ACCEPT' | 'REJECT' | 'CONDITIONAL_FLAG') => {
    if (!activeRecord) return;
    const logEntry = {
      operator_id: operatorId,
      action: `TACTILE_${action}`,
      notes: `Operator validated action on HMI panel. Strip released under operator sign-off.`,
      timestamp: new Date().toISOString()
    };
    const updated = {
      ...activeRecord,
      decision: action as any,
      operator_logs: [...(activeRecord.operator_logs || []), logEntry]
    };
    setActiveRecord(updated);
    setActiveHistory((prev) => prev.map((h) => (h.inspection_id === updated.inspection_id ? updated : h)));
    onOverrideInspection(updated.inspection_id, action, operatorId, logEntry.notes);
    setNotificationToast({
      title: `OPERATOR ACTION: ${action}`,
      message: `Inspection ${updated.inspection_id} marked as ${action} by ${operatorId}.`,
      type: 'success'
    });
  };

  // Submit Formal ISO 9001 Override
  const handleSubmitFormalOverride = () => {
    if (!overrideTargetRecord) return;
    const finalDecision =
      overrideActionType === 'OVERRIDE_ACCEPT'
        ? 'ACCEPT'
        : overrideActionType === 'OVERRIDE_REJECT'
        ? 'REJECT'
        : overrideTargetRecord.decision;

    const logEntry = {
      operator_id: overrideBadgeInput,
      action: overrideActionType,
      notes: `[Reason: ${overrideReasonCode}] ${overrideNotesInput}`,
      timestamp: new Date().toISOString()
    };

    const updated: InspectionRecord = {
      ...overrideTargetRecord,
      decision: finalDecision as any,
      operator_logs: [...(overrideTargetRecord.operator_logs || []), logEntry]
    };

    setActiveRecord(updated);
    setActiveHistory((prev) => prev.map((h) => (h.inspection_id === updated.inspection_id ? updated : h)));
    onOverrideInspection(updated.inspection_id, overrideActionType, overrideBadgeInput, logEntry.notes);
    setOverrideModalOpen(false);

    setNotificationToast({
      title: 'ISO 9001 AUDIT LOGGED',
      message: `Override registered under Badge ${overrideBadgeInput}. Reason: ${overrideReasonCode}`,
      type: 'success'
    });
  };

  // KPI calculations
  const totalInspections = activeHistory.length;
  const acceptedCount = activeHistory.filter((h) => h.decision === 'ACCEPT').length;
  const rejectedCount = activeHistory.filter((h) => h.decision === 'REJECT').length;
  const manualCount = activeHistory.filter((h) => h.decision === 'MANUAL_REVIEW').length;
  const flaggedCount = activeHistory.filter((h) => h.decision === 'CONDITIONAL_FLAG').length;
  const defectRate = totalInspections > 0 ? (((rejectedCount + flaggedCount) / totalInspections) * 100).toFixed(1) : '0.0';

  // Defect category distribution counts
  const categoryCounts: Record<string, number> = {
    crazing: 0,
    inclusion: 0,
    patches: 0,
    pitted_surface: 0,
    rolled_in_scale: 0,
    scratches: 0,
    normal: 0
  };
  activeHistory.forEach((h) => {
    const key = h.defect_type.toLowerCase();
    if (categoryCounts[key] !== undefined) {
      categoryCounts[key]++;
    }
  });

  return (
    <div className="space-y-6">
      {/* 1. TOP INDUSTRIAL STATUS RIBBON & HMI CONTROL BAR */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Left: Line Status Badge & Interlock */}
          <div className="flex items-center gap-3">
            <div
              className={`px-3.5 py-1.5 rounded-lg border text-xs font-black tracking-wider flex items-center gap-2 ${
                lineStatus === 'RUNNING'
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 animate-pulse'
                  : lineStatus === 'PAUSED'
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                  : 'bg-rose-600 text-white border-rose-500 animate-bounce shadow-lg shadow-rose-600/40'
              }`}
            >
              <Radio className={`w-4 h-4 ${lineStatus === 'RUNNING' ? 'animate-spin' : ''}`} />
              LINE STATUS: {lineStatus}
            </div>

            {/* Quick Pause / Resume Toggle */}
            {lineStatus !== 'E-STOP' ? (
              <button
                onClick={() => setLineStatus(lineStatus === 'RUNNING' ? 'PAUSED' : 'RUNNING')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold border border-slate-700 transition"
              >
                {lineStatus === 'RUNNING' ? (
                  <>
                    <Pause className="w-3.5 h-3.5 text-amber-400" /> PAUSE LINE
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 text-emerald-400" /> RESUME FEED
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={() => {
                  setLineStatus('PAUSED');
                  setNotificationToast({
                    title: 'INTERLOCK RESET',
                    message: 'Drive interlock cleared. Line is now PAUSED and ready for restart.',
                    type: 'warn'
                  });
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition shadow"
              >
                <RotateCcw className="w-3.5 h-3.5" /> RESET SAFETY INTERLOCK
              </button>
            )}

            <div className="h-6 w-px bg-slate-800 hidden sm:block" />

            {/* Line Rolling Speed Slider */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 font-mono text-[11px] font-semibold">SPEED:</span>
              <input
                type="range"
                min="0.8"
                max="4.5"
                step="0.1"
                value={lineSpeed}
                disabled={lineStatus !== 'RUNNING'}
                onChange={(e) => setLineSpeed(parseFloat(e.target.value))}
                className="w-24 accent-cyan-500 cursor-pointer disabled:opacity-40"
              />
              <span className="font-mono font-bold text-cyan-400 text-xs w-14">
                {lineSpeed.toFixed(1)} m/s
              </span>
            </div>
          </div>

          {/* Right: Active Coil, Operator Badge & Audio Buzzer Toggle */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="bg-slate-950 px-3 py-1 rounded-lg border border-slate-800 text-[11px] font-mono">
              <span className="text-slate-500">COIL: </span>
              <span className="text-slate-200 font-bold">{activeCoilId}</span>
              <span className="text-slate-500 ml-2">GAUGE: </span>
              <span className="text-emerald-400 font-bold">0.85 mm</span>
            </div>

            <div className="bg-slate-950 px-3 py-1 rounded-lg border border-slate-800 text-[11px] font-mono flex items-center gap-1.5">
              <Lock className="w-3 h-3 text-cyan-400" />
              <span className="text-slate-500">OPERATOR: </span>
              <span className="text-cyan-300 font-bold">{operatorId}</span>
            </div>

            {/* Audio Buzzer Alarm Toggle */}
            <button
              onClick={() => {
                const nextState = !audioAlarmEnabled;
                setAudioAlarmEnabled(nextState);
                if (nextState) playBuzzer('alert');
              }}
              className={`p-2 rounded-lg border transition ${
                audioAlarmEnabled
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/40 hover:bg-purple-500/30'
                  : 'bg-slate-800 text-slate-500 border-slate-700'
              }`}
              title={audioAlarmEnabled ? 'Buzzer Alarm Enabled (Click to Mute)' : 'Buzzer Muted'}
            >
              {audioAlarmEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>

            {/* Auto Feed Toggle */}
            <button
              onClick={() => setAutoInspectInterval(!autoInspectInterval)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
                autoInspectInterval
                  ? 'bg-cyan-500 text-slate-950 border-cyan-400'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${autoInspectInterval ? 'animate-spin' : ''}`} />
              {autoInspectInterval ? 'AUTO-INSPECT ON' : 'AUTO-INSPECT'}
            </button>

            {/* Trigger Next Specimen Button */}
            <button
              onClick={handleInspectNextPreset}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-md shadow-emerald-600/20 transition active:scale-95"
            >
              <Zap className="w-3.5 h-3.5" />
              INSPECT SPECIMEN
            </button>
          </div>
        </div>
      </div>

      {/* Floating Notification Toast */}
      {notificationToast && (
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between text-xs shadow-2xl transition-all ${
            notificationToast.type === 'critical'
              ? 'bg-rose-950/90 border-rose-500 text-rose-200'
              : notificationToast.type === 'warn'
              ? 'bg-amber-950/90 border-amber-500 text-amber-200'
              : 'bg-emerald-950/90 border-emerald-500 text-emerald-200'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {notificationToast.type === 'critical' ? (
              <AlertOctagon className="w-5 h-5 text-rose-400 shrink-0 animate-pulse" />
            ) : notificationToast.type === 'warn' ? (
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            )}
            <div>
              <div className="font-bold tracking-wide">{notificationToast.title}</div>
              <div className="text-[11px] opacity-90">{notificationToast.message}</div>
            </div>
          </div>
          <button
            onClick={() => setNotificationToast(null)}
            className="p-1 rounded hover:bg-white/10 text-slate-300"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 2. MAIN INSPECTION VIEWPORT & TACTILE ACTION STATION */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 cols): Conveyor Canvas Viewport + Tactile Controls */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3 shadow-lg">
            {/* Viewport Header Controls */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <Camera className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Live Strip Inspection Stream
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  FOV: 200mm Calibrated Cross-Section
                </span>
              </div>

              {/* View Overlay Mode Selector */}
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                <button
                  onClick={() => setSelectedOverlayView('boxes')}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                    selectedOverlayView === 'boxes'
                      ? 'bg-cyan-500 text-slate-950'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Bounding Box
                </button>
                <button
                  onClick={() => setSelectedOverlayView('heatmap')}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                    selectedOverlayView === 'heatmap'
                      ? 'bg-cyan-500 text-slate-950'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Anomaly Heatmap
                </button>
                <button
                  onClick={() => setSelectedOverlayView('raw')}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                    selectedOverlayView === 'raw'
                      ? 'bg-cyan-500 text-slate-950'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Raw Surface
                </button>

                <div className="h-4 w-px bg-slate-800 mx-1" />

                <button
                  onClick={() => setIsFrozen(!isFrozen)}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold flex items-center gap-1 ${
                    isFrozen ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Eye className="w-3 h-3" />
                  {isFrozen ? 'FROZEN' : 'FREEZE'}
                </button>
              </div>
            </div>

            {/* Input Feed Source Selector Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-slate-400 uppercase font-semibold">Feed Input:</span>
                <div className="flex items-center gap-1 bg-slate-900 p-0.5 rounded border border-slate-800">
                  <button
                    onClick={() => {
                      setStreamSource('conveyor');
                      handleStopWebcam();
                    }}
                    className={`px-2.5 py-1 rounded text-[11px] font-medium transition ${
                      streamSource === 'conveyor'
                        ? 'bg-cyan-500 text-slate-950 font-bold'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Conveyor Sim
                  </button>
                  <button
                    onClick={() => {
                      if (streamSource === 'webcam' && webcamStreaming) {
                        handleStopWebcam();
                        setStreamSource('conveyor');
                      } else {
                        handleStartWebcam();
                      }
                    }}
                    className={`px-2.5 py-1 rounded text-[11px] font-medium transition flex items-center gap-1.5 ${
                      streamSource === 'webcam' && webcamStreaming
                        ? 'bg-rose-500 text-white font-bold'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <Camera className="w-3 h-3" />
                    {streamSource === 'webcam' && webcamStreaming ? 'Stop Webcam' : 'Web Camera'}
                  </button>
                  <button
                    onClick={() => {
                      setStreamSource('upload');
                      handleStopWebcam();
                      fileInputRef.current?.click();
                    }}
                    className={`px-2.5 py-1 rounded text-[11px] font-medium transition flex items-center gap-1.5 ${
                      streamSource === 'upload'
                        ? 'bg-emerald-500 text-slate-950 font-bold'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <Upload className="w-3 h-3" />
                    Upload Image
                  </button>
                </div>
              </div>

              {/* Action buttons for live feed / uploaded image */}
              <div className="flex items-center gap-2">
                {streamSource === 'webcam' && (
                  <button
                    onClick={handleInspectLiveCanvas}
                    disabled={!webcamStreaming || isProcessingInspection}
                    className="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-[11px] font-bold rounded flex items-center gap-1.5 shadow"
                  >
                    <Crosshair className="w-3 h-3" />
                    {isProcessingInspection ? 'Inspecting...' : 'Inspect Camera Frame'}
                  </button>
                )}

                {streamSource === 'upload' && (
                  <>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium rounded border border-slate-700 flex items-center gap-1"
                    >
                      <Upload className="w-3 h-3" />
                      {uploadedFileName ? 'Change Image' : 'Select Image'}
                    </button>
                    {uploadedImage && (
                      <button
                        onClick={handleInspectLiveCanvas}
                        disabled={isProcessingInspection}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold rounded flex items-center gap-1.5 shadow"
                      >
                        <Crosshair className="w-3 h-3" />
                        {isProcessingInspection ? 'Inspecting...' : 'Inspect Specimen'}
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Error banner if webcam fails */}
            {webcamError && (
              <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-lg flex items-start gap-2 text-xs text-rose-300">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold">{webcamError}</div>
                  <div className="text-[11px] text-rose-400/80">
                    If camera permission is restricted in this environment, you can use the <strong>Upload Image</strong> option or <strong>Camera & HUD</strong> station tab to inspect any metal surface photograph.
                  </div>
                </div>
              </div>
            )}

            {/* Hidden Video & File Picker Elements */}
            <video ref={videoRef} playsInline muted autoPlay className="hidden" />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileUpload}
              className="hidden"
            />

            {/* Industrial Canvas Viewport */}
            <div className="relative rounded-lg overflow-hidden border border-slate-800 bg-slate-950 flex items-center justify-center">
              <canvas
                ref={canvasRef}
                width={720}
                height={360}
                className="w-full h-auto max-h-[380px] block cursor-crosshair"
              />

              {/* Reticle HUD overlay on top-right */}
              <div className="absolute top-3 right-3 bg-slate-950/80 backdrop-blur-sm border border-slate-800 rounded-lg p-2.5 text-[11px] font-mono space-y-1 text-slate-300">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500">LATENCY:</span>
                  <span className="text-emerald-400 font-bold">{activeRecord.inference_ms || 34.2} ms</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500">CONFIDENCE:</span>
                  <span className="text-cyan-400 font-bold">{(activeRecord.confidence * 100).toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-slate-500">ZONE:</span>
                  <span className="text-amber-400 font-bold">{activeRecord.location}</span>
                </div>
              </div>

              {/* Emergency Stop Visual Bar if active */}
              {lineStatus === 'E-STOP' && (
                <div className="absolute inset-0 bg-rose-950/80 backdrop-blur-sm flex flex-col items-center justify-center space-y-3 z-10">
                  <AlertOctagon className="w-16 h-16 text-rose-500 animate-bounce" />
                  <div className="text-xl font-black text-white tracking-widest uppercase">
                    EMERGENCY STOP INTERLOCK ENGAGED
                  </div>
                  <div className="text-xs text-rose-200 max-w-md text-center">
                    All rolling drives and uncoilers are electro-mechanically isolated. Clear foreign obstruction and press RESET INTERLOCK to resume.
                  </div>
                </div>
              )}
            </div>

            {/* Tactical Specimen Preset Selector Strip */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
              <span className="text-slate-500 font-mono text-[10px] uppercase font-bold mr-1">
                Inject Defect Specimen:
              </span>
              {CONVEYOR_SPECIMENS.map((spec, i) => (
                <button
                  key={spec.type}
                  onClick={() => {
                    setSpecimenCursor(i);
                    const now = new Date();
                    const newRecord: InspectionRecord = {
                      inspection_id: `INS-2026-${String(activeHistory.length + 1).padStart(3, '0')}`,
                      product_id: `STEEL-${spec.type.substring(0, 2).toUpperCase()}-${Math.floor(100 + Math.random() * 900)}`,
                      timestamp: now.toISOString(),
                      defect_detected: spec.type !== 'normal',
                      defect_type: spec.type,
                      severity: spec.severity,
                      confidence: spec.confidence,
                      location: spec.location,
                      decision: spec.decision,
                      recommendation: spec.recommendation,
                      inference_ms: +(31 + Math.random() * 8).toFixed(1),
                      boxes:
                        spec.type !== 'normal'
                          ? [
                              {
                                class_name: spec.type,
                                confidence: spec.confidence,
                                xmin: spec.box.xmin,
                                ymin: spec.box.ymin,
                                xmax: spec.box.xmax,
                                ymax: spec.box.ymax,
                                area_ratio: +(((spec.box.xmax - spec.box.xmin) * (spec.box.ymax - spec.box.ymin)) / 60000).toFixed(3),
                                severity: spec.severity
                              }
                            ]
                          : [],
                      root_cause: spec.root_cause,
                      implications: spec.implications,
                      remediation_steps: spec.remediation_steps,
                      shift_log_summary: `${spec.decision}: ${spec.type.toUpperCase()} in ${spec.location}.`
                    };
                    setActiveRecord(newRecord);
                    setActiveHistory((prev) => [newRecord, ...prev]);
                    onAddInspection(newRecord);
                    if (spec.severity === 'Critical' || spec.severity === 'High') playBuzzer('critical');
                  }}
                  className={`px-2 py-1 rounded text-[11px] font-medium border transition ${
                    activeRecord.defect_type === spec.type
                      ? 'bg-slate-700 text-white border-cyan-400 font-bold'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  {spec.name}
                </button>
              ))}
            </div>
          </div>

          {/* TACTILE INDUSTRIAL ACTION PANEL & E-STOP BUTTON */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h3 className="text-xs font-black text-white uppercase tracking-wider flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-emerald-400" />
                  Tactile Operator Action Console (HMI Station)
                </h3>
                <p className="text-[11px] text-slate-400">
                  Direct physical-style inputs with immediate PLC interlock and ISO 9001 audit recording.
                </p>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30">
                ACTIVE COIL: {activeCoilId}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {/* Button 1: ACCEPT & RELEASE */}
              <button
                onClick={() => handleOperatorAction('ACCEPT')}
                className="group relative flex flex-col items-center justify-center p-3.5 rounded-xl bg-gradient-to-b from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white shadow-lg shadow-emerald-700/30 active:translate-y-0.5 transition border-t border-emerald-400"
              >
                <CheckCircle2 className="w-6 h-6 mb-1 text-emerald-100" />
                <span className="text-xs font-black tracking-wide">ACCEPT &amp; CLEAR</span>
                <span className="text-[9px] text-emerald-200 font-mono">PASS TO SLITTER</span>
              </button>

              {/* Button 2: FLAG FOR REWORK */}
              <button
                onClick={() => handleOperatorAction('CONDITIONAL_FLAG')}
                className="group relative flex flex-col items-center justify-center p-3.5 rounded-xl bg-gradient-to-b from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 text-white shadow-lg shadow-amber-700/30 active:translate-y-0.5 transition border-t border-amber-400"
              >
                <AlertTriangle className="w-6 h-6 mb-1 text-amber-100" />
                <span className="text-xs font-black tracking-wide">FLAG / REWORK</span>
                <span className="text-[9px] text-amber-200 font-mono">DIVERT TO BUFFER</span>
              </button>

              {/* Button 3: QUARANTINE / REJECT */}
              <button
                onClick={() => handleOperatorAction('REJECT')}
                className="group relative flex flex-col items-center justify-center p-3.5 rounded-xl bg-gradient-to-b from-rose-700 to-rose-800 hover:from-rose-600 hover:to-rose-700 text-white shadow-lg shadow-rose-800/30 active:translate-y-0.5 transition border-t border-rose-400"
              >
                <XCircle className="w-6 h-6 mb-1 text-rose-100" />
                <span className="text-xs font-black tracking-wide">REJECT / SCRAP</span>
                <span className="text-[9px] text-rose-200 font-mono">AUTO-QUARANTINE</span>
              </button>

              {/* Button 4: FORMAL MANUAL OVERRIDE */}
              <button
                onClick={() => {
                  setOverrideTargetRecord(activeRecord);
                  setOverrideModalOpen(true);
                }}
                className="group relative flex flex-col items-center justify-center p-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 shadow-md active:translate-y-0.5 transition border border-slate-700"
              >
                <Lock className="w-6 h-6 mb-1 text-cyan-400" />
                <span className="text-xs font-black tracking-wide">MANUAL OVERRIDE</span>
                <span className="text-[9px] text-cyan-300 font-mono">ISO 9001 AUDIT</span>
              </button>
            </div>

            {/* BIG EMERGENCY STOP PUSH-BUTTON (E-STOP) */}
            <div className="pt-2 flex items-center justify-between border-t border-slate-800">
              <div className="flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  SAFETY CIRCUIT: <span className="text-emerald-400 font-bold">ARMED &amp; MONITORED</span>
                </span>
              </div>

              <button
                onClick={handleEmergencyStop}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-b from-red-600 via-red-700 to-red-800 hover:from-red-500 hover:to-red-700 text-white text-xs font-black tracking-wider uppercase border-2 border-red-500 shadow-xl shadow-red-700/40 active:scale-95 transition"
              >
                <AlertOctagon className="w-5 h-5 text-white animate-pulse" />
                EMERGENCY STOP (E-STOP)
              </button>
            </div>
          </div>
        </div>

        {/* Right Column (4 cols): Active Defect Assessment & Advisory */}
        <div className="lg:col-span-4 space-y-4">
          {/* Active Inspection Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase text-slate-500">Active Specimen</span>
                <h4 className="text-base font-bold text-white flex items-center gap-2">
                  {activeRecord.product_id}
                </h4>
              </div>

              {/* Big Decision Badge */}
              <div
                className={`px-3 py-1.5 rounded-lg font-black text-xs tracking-wider border shadow-sm ${
                  activeRecord.decision === 'ACCEPT'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                    : activeRecord.decision === 'REJECT'
                    ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
                    : activeRecord.decision === 'CONDITIONAL_FLAG'
                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                    : 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                }`}
              >
                {activeRecord.decision}
              </div>
            </div>

            {/* Specimen Telemetry Grid */}
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Defect Class</div>
                <div className="font-bold text-white capitalize">{activeRecord.defect_type}</div>
              </div>

              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Confidence</div>
                <div className="font-bold text-cyan-400">{(activeRecord.confidence * 100).toFixed(1)}%</div>
              </div>

              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Severity Tier</div>
                <div
                  className={`font-bold ${
                    activeRecord.severity === 'Critical'
                      ? 'text-rose-400'
                      : activeRecord.severity === 'High'
                      ? 'text-orange-400'
                      : activeRecord.severity === 'Medium'
                      ? 'text-amber-400'
                      : 'text-emerald-400'
                  }`}
                >
                  {activeRecord.severity}
                </div>
              </div>

              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Surface Zone</div>
                <div className="font-bold text-slate-200 truncate">{activeRecord.location}</div>
              </div>
            </div>

            {/* Fail-Safe Alert if confidence < 0.65 */}
            {activeRecord.confidence < 0.65 && (
              <div className="p-3 bg-purple-950/40 border border-purple-500/40 rounded-lg text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-purple-300">
                  <AlertTriangle className="w-4 h-4 text-purple-400" />
                  FAIL-SAFE INTERLOCK ENGAGED
                </div>
                <div className="text-[11px] text-slate-300">
                  Model confidence ({(activeRecord.confidence * 100).toFixed(1)}%) is under the 65% automatic disposition cutoff. Automated scrap rejected; manual inspection required.
                </div>
              </div>
            )}

            {/* AI Advisory Summary (Llama 3.2 ExecuTorch) */}
            <div className="space-y-2 pt-1 border-t border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5" />
                  Llama 3.2 Edge Metallurgical Advisory
                </span>
                <span className="text-[9px] font-mono text-slate-500">ExecuTorch Arm64</span>
              </div>

              <div className="p-3 bg-purple-950/20 border border-purple-900/40 rounded-lg text-xs space-y-2">
                <div>
                  <span className="text-slate-400 text-[10px] uppercase font-bold block">Root Cause Diagnosis:</span>
                  <p className="text-slate-200 text-[11px] leading-relaxed">
                    {activeRecord.root_cause || 'Uniform crystal grain matrix under nominal cold-rolling shear stress.'}
                  </p>
                </div>

                <div>
                  <span className="text-slate-400 text-[10px] uppercase font-bold block">Metallurgical Impact:</span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">
                    {activeRecord.implications || 'Standard mechanical compliance with ASTM A1008 deep drawing.'}
                  </p>
                </div>

                {activeRecord.remediation_steps && activeRecord.remediation_steps.length > 0 && (
                  <div>
                    <span className="text-slate-400 text-[10px] uppercase font-bold block">Operator Action Checklist:</span>
                    <ul className="list-disc list-inside text-[11px] text-emerald-300 space-y-0.5">
                      {activeRecord.remediation_steps.map((step, idx) => (
                        <li key={idx}>{step}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions: Inspection Certificate */}
            <div className="pt-2 flex gap-2">
              <button
                onClick={() => {
                  setCertificateRecord(activeRecord);
                  setCertificateModalOpen(true);
                }}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold border border-slate-700 transition"
              >
                <FileText className="w-3.5 h-3.5 text-cyan-400" />
                Inspection Certificate
              </button>

              <button
                onClick={() => {
                  setOverrideTargetRecord(activeRecord);
                  setOverrideModalOpen(true);
                }}
                className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition"
                title="Log ISO 9001 Manual Review"
              >
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. QUALITY KPI GAUGES & DEFECT DISTRIBUTION */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* KPI 1: Total Inspected */}
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase font-semibold">Total Inspected Specimen</div>
          <div className="text-2xl font-black text-white flex items-center justify-between">
            <span>{totalInspections}</span>
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          <div className="text-[10px] text-slate-500 font-mono">SQLite WAL Transaction Log</div>
        </div>

        {/* KPI 2: Accepted vs Rejected */}
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase font-semibold">Accepted / Released</div>
          <div className="text-2xl font-black text-emerald-400 flex items-center justify-between">
            <span>{acceptedCount}</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            {totalInspections > 0 ? ((acceptedCount / totalInspections) * 100).toFixed(1) : 0}% Yield Rate
          </div>
        </div>

        {/* KPI 3: Rejections & Scraps */}
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase font-semibold">Rejected &amp; Flagged</div>
          <div className="text-2xl font-black text-rose-400 flex items-center justify-between">
            <span>{rejectedCount + flaggedCount}</span>
            <XCircle className="w-5 h-5 text-rose-400" />
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            {rejectedCount} Rejected, {flaggedCount} Rework
          </div>
        </div>

        {/* KPI 4: Overall Defect Rate */}
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase font-semibold">Line Defect Rate</div>
          <div className="text-2xl font-black text-amber-400 flex items-center justify-between">
            <span>{defectRate}%</span>
            <TrendingUp className="w-5 h-5 text-amber-400" />
          </div>
          <div className="text-[10px] text-slate-500 font-mono">Threshold Target: &lt; 3.0%</div>
        </div>
      </div>

      {/* 4. DEFECT CATEGORY DISTRIBUTION & RECENT INSPECTION TICKER */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Defect Category Distribution Bars (5 cols) */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-xs font-black text-white uppercase tracking-wider flex items-center gap-2">
                <Gauge className="w-4 h-4 text-cyan-400" />
                NEU-DET Defect Category Distribution
              </h4>
              <p className="text-[11px] text-slate-400">Class breakdown across current production batch.</p>
            </div>
            <span className="text-[10px] font-mono text-slate-500">6 NEU Classes</span>
          </div>

          <div className="space-y-2.5">
            {[
              { id: 'crazing', label: 'Crazing', color: 'bg-rose-500' },
              { id: 'inclusion', label: 'Inclusion', color: 'bg-orange-500' },
              { id: 'patches', label: 'Patches', color: 'bg-amber-500' },
              { id: 'pitted_surface', label: 'Pitted Surface', color: 'bg-yellow-500' },
              { id: 'rolled_in_scale', label: 'Rolled-in Scale', color: 'bg-red-500' },
              { id: 'scratches', label: 'Scratches', color: 'bg-blue-500' },
              { id: 'normal', label: 'Defect-Free (Normal)', color: 'bg-emerald-500' }
            ].map((cat) => {
              const count = categoryCounts[cat.id] || 0;
              const pct = totalInspections > 0 ? (count / totalInspections) * 100 : 0;
              return (
                <div key={cat.id} className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300 font-medium">{cat.label}</span>
                    <span className="text-slate-400">
                      {count} ({pct.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                    <div
                      className={`h-full ${cat.color} transition-all duration-500`}
                      style={{ width: `${Math.max(pct, count > 0 ? 3 : 0)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Recent Inspection Records Ticker (7 cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-xs font-black text-white uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                Live Inspection Telemetry Stream
              </h4>
              <p className="text-[11px] text-slate-400">Latest strip specimens logged by the edge inference pipeline.</p>
            </div>

            <button
              onClick={() => {
                const csvHeader = 'inspection_id,product_id,defect_detected,defect_type,severity,confidence,decision,timestamp\n';
                const csvRows = activeHistory
                  .map(
                    (h) =>
                      `"${h.inspection_id}","${h.product_id}",${h.defect_detected},"${h.defect_type}","${h.severity}",${h.confidence},"${h.decision}","${h.timestamp}"`
                  )
                  .join('\n');
                const blob = new Blob([csvHeader + csvRows], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `qualiedge_shift_inspection_${Date.now()}.csv`;
                a.click();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition"
            >
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </button>
          </div>

          <div className="overflow-x-auto max-h-[290px] overflow-y-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-[10px] font-mono text-slate-400 uppercase bg-slate-950/60 sticky top-0">
                  <th className="py-2 px-3">ID / Serial</th>
                  <th className="py-2 px-3">Class</th>
                  <th className="py-2 px-3">Severity</th>
                  <th className="py-2 px-3">Confidence</th>
                  <th className="py-2 px-3">Decision</th>
                  <th className="py-2 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {activeHistory.map((item) => (
                  <tr
                    key={item.inspection_id}
                    onClick={() => setActiveRecord(item)}
                    className={`cursor-pointer transition hover:bg-slate-800/40 ${
                      activeRecord.inspection_id === item.inspection_id ? 'bg-cyan-500/10' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3">
                      <div className="font-bold text-white">{item.product_id}</div>
                      <div className="text-[10px] text-slate-500">{item.inspection_id}</div>
                    </td>
                    <td className="py-2.5 px-3 capitalize text-slate-300">{item.defect_type}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          item.severity === 'Critical'
                            ? 'bg-rose-500/20 text-rose-300'
                            : item.severity === 'High'
                            ? 'bg-orange-500/20 text-orange-300'
                            : item.severity === 'Medium'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-emerald-500/20 text-emerald-300'
                        }`}
                      >
                        {item.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-cyan-400">{(item.confidence * 100).toFixed(1)}%</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          item.decision === 'ACCEPT'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : item.decision === 'REJECT'
                            ? 'bg-rose-500/20 text-rose-300'
                            : item.decision === 'CONDITIONAL_FLAG'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-purple-500/20 text-purple-300'
                        }`}
                      >
                        {item.decision}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOverrideTargetRecord(item);
                          setOverrideModalOpen(true);
                        }}
                        className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-bold"
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 5. FORMAL ISO 9001 OVERRIDE MODAL */}
      {overrideModalOpen && overrideTargetRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white">ISO 9001 Quality Operator Review</h3>
              </div>
              <button
                onClick={() => setOverrideModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 text-xs font-mono space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500">Record ID:</span>
                <span className="text-white font-bold">{overrideTargetRecord.inspection_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Product Serial:</span>
                <span className="text-cyan-400 font-bold">{overrideTargetRecord.product_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">AI Model Verdict:</span>
                <span className="text-rose-400 font-bold">
                  {overrideTargetRecord.decision} ({overrideTargetRecord.defect_type} - {(overrideTargetRecord.confidence * 100).toFixed(1)}%)
                </span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wide mb-1.5">
                  Authorized Override Action
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setOverrideActionType('OVERRIDE_ACCEPT')}
                    className={`py-2 px-3 rounded-lg font-bold border transition text-center ${
                      overrideActionType === 'OVERRIDE_ACCEPT'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500'
                        : 'bg-slate-950 text-slate-400 border-slate-800'
                    }`}
                  >
                    OVERRIDE ACCEPT
                  </button>
                  <button
                    type="button"
                    onClick={() => setOverrideActionType('OVERRIDE_REJECT')}
                    className={`py-2 px-3 rounded-lg font-bold border transition text-center ${
                      overrideActionType === 'OVERRIDE_REJECT'
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500'
                        : 'bg-slate-950 text-slate-400 border-slate-800'
                    }`}
                  >
                    CONFIRM REJECT
                  </button>
                  <button
                    type="button"
                    onClick={() => setOverrideActionType('VERIFIED')}
                    className={`py-2 px-3 rounded-lg font-bold border transition text-center ${
                      overrideActionType === 'VERIFIED'
                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500'
                        : 'bg-slate-950 text-slate-400 border-slate-800'
                    }`}
                  >
                    VERIFIED PASS
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wide mb-1">
                  Operator Badge ID
                </label>
                <input
                  type="text"
                  value={overrideBadgeInput}
                  onChange={(e) => setOverrideBadgeInput(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-xs text-white rounded-lg p-2.5 font-mono focus:outline-none focus:border-cyan-500"
                  placeholder="OP-4482"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wide mb-1">
                  Justification / Reason Code
                </label>
                <select
                  value={overrideReasonCode}
                  onChange={(e) => setOverrideReasonCode(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-xs text-white rounded-lg p-2.5 focus:outline-none focus:border-cyan-500"
                >
                  <option value="SURFACE_PROFILOMETRY_PASS">Surface Profilometry Pass (&lt;0.05mm roughness)</option>
                  <option value="FALSE_POSITIVE_GLARE">Optical Specular Glare / Harmless Oil Sheen</option>
                  <option value="SECONDARY_REWORK_BUFFER">Diverted to Buffing Table for Polishing</option>
                  <option value="STRUCTURAL_NON_EXPOSED">Downgraded to Non-Exposed Auto Underbody Grade</option>
                  <option value="METALLURGIST_APPROVAL">Signed Shift Metallurgist Engineering Waiver</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wide mb-1">
                  Technical Audit Notes
                </label>
                <textarea
                  rows={3}
                  value={overrideNotesInput}
                  onChange={(e) => setOverrideNotesInput(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-xs text-white rounded-lg p-2.5 focus:outline-none focus:border-cyan-500"
                  placeholder="Enter detailed measurement data and tool calibration date..."
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setOverrideModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmitFormalOverride}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition"
              >
                Sign &amp; Commit Override to Database
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. INSPECTION CERTIFICATE REPORT MODAL */}
      {certificateModalOpen && certificateRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">Quality Inspection Certificate</h3>
              </div>
              <button
                onClick={() => setCertificateModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Certificate Body (Print-like document) */}
            <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 font-mono text-xs text-slate-300 space-y-4">
              <div className="text-center border-b border-slate-800 pb-3 space-y-1">
                <div className="text-sm font-black text-white tracking-widest">
                  BHARAT AI SOC CHALLENGE 2026–27 | QUALIEDGE QC
                </div>
                <div className="text-[10px] text-slate-400">
                  Automated Cold-Rolled Steel Strip Surface Quality Inspection Report
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-[11px]">
                <div>
                  <span className="text-slate-500 block">Inspection Certificate ID:</span>
                  <span className="text-cyan-400 font-bold">{certificateRecord.inspection_id}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Timestamp (ISO 8601):</span>
                  <span className="text-white font-bold">{certificateRecord.timestamp}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Product Serial Batch:</span>
                  <span className="text-white font-bold">{certificateRecord.product_id}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Steel Alloy Standard:</span>
                  <span className="text-white font-bold">ASTM A1008 CS Type B (0.85 mm)</span>
                </div>
              </div>

              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-bold uppercase text-[10px]">Quality Gate Verdict:</span>
                  <span
                    className={`font-black text-sm px-2.5 py-0.5 rounded ${
                      certificateRecord.decision === 'ACCEPT'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : certificateRecord.decision === 'REJECT'
                        ? 'bg-rose-500/20 text-rose-400'
                        : 'bg-amber-500/20 text-amber-400'
                    }`}
                  >
                    {certificateRecord.decision}
                  </span>
                </div>

                <div className="text-[11px] space-y-1">
                  <div>
                    <span className="text-slate-500">Defect Classification: </span>
                    <span className="text-white capitalize font-bold">{certificateRecord.defect_type}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Severity Tier: </span>
                    <span className="text-amber-400 font-bold">{certificateRecord.severity}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Model Confidence: </span>
                    <span className="text-cyan-400 font-bold">{(certificateRecord.confidence * 100).toFixed(2)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Location Coordinates: </span>
                    <span className="text-slate-200">{certificateRecord.location}</span>
                  </div>
                </div>
              </div>

              {/* Llama Root Cause Summary */}
              <div>
                <span className="text-purple-400 font-bold block text-[10px] uppercase">
                  ExecuTorch Metallurgical Diagnosis:
                </span>
                <p className="text-[11px] text-slate-300 leading-relaxed mt-1">
                  {certificateRecord.root_cause || 'Uniform crystal grain structure conforming to surface finish requirements.'}
                </p>
              </div>

              {/* Operator Audit Trail */}
              {certificateRecord.operator_logs && certificateRecord.operator_logs.length > 0 && (
                <div className="border-t border-slate-800 pt-2 space-y-1">
                  <span className="text-emerald-400 font-bold text-[10px] uppercase">Operator Audit Logs:</span>
                  {certificateRecord.operator_logs.map((log, i) => (
                    <div key={i} className="text-[10px] text-slate-400">
                      [{log.timestamp}] <span className="text-cyan-300">{log.operator_id}</span> ({log.action}): {log.notes}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setCertificateModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold shadow-lg shadow-cyan-600/30 transition flex items-center gap-1.5"
              >
                <Download className="w-4 h-4" />
                Print / Save PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
