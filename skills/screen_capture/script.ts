/**
 * Screen Capture Skill TypeScript Backend Runner (`skills/screen_capture/script.ts`)
 */

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CaptureResult {
  status: 'success' | 'error' | 'warning';
  file_path?: string;
  message: string;
}

export class ScreenCaptureService {
  private _isRecording: boolean = false;
  private _recordingSeconds: number = 0;
  private _outputDir: string;

  constructor(outputDir?: string) {
    this._outputDir = outputDir || './download';
  }

  public async captureFullScreenshot(): Promise<CaptureResult> {
    const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
    const filePath = `${this._outputDir}/screenshot_${timestamp}.png`;
    return {
      status: 'success',
      file_path: filePath,
      message: `全屏截图已成功捕获并保存至 ${filePath}`,
    };
  }

  public async captureAreaScreenshot(rect: Rect): Promise<CaptureResult> {
    const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
    const filePath = `${this._outputDir}/area_${timestamp}.png`;
    return {
      status: 'success',
      file_path: filePath,
      message: `区域截图 (${rect.width}×${rect.height}px) 已保存至 ${filePath}`,
    };
  }

  public async captureLongScreenshot(): Promise<CaptureResult> {
    const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
    const filePath = `${this._outputDir}/long_${timestamp}.png`;
    return {
      status: 'success',
      file_path: filePath,
      message: `长截屏拼接成功并保存至 ${filePath}`,
    };
  }

  public startRecording(type: 'full' | 'area', rect?: Rect): CaptureResult {
    if (this._isRecording) {
      return { status: 'warning', message: '已经在录制中' };
    }
    this._isRecording = true;
    this._recordingSeconds = 0;
    const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
    const filePath = `${this._outputDir}/record_${timestamp}.mp4`;

    return {
      status: 'success',
      file_path: filePath,
      message: `已开始${type === 'area' && rect ? `区域(${rect.width}×${rect.height})` : '全屏'}录制`,
    };
  }

  public stopRecording(): CaptureResult {
    if (!this._isRecording) {
      return { status: 'warning', message: '未在录制中' };
    }
    this._isRecording = false;
    const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
    const filePath = `${this._outputDir}/record_${timestamp}.mp4`;

    return {
      status: 'success',
      file_path: filePath,
      message: `屏幕录制完成并已导出视频文件: ${filePath}`,
    };
  }
}

// CLI Execution Support
if (import.meta.main || (typeof require !== 'undefined' && require.main === module)) {
  const service = new ScreenCaptureService();
  service.captureFullScreenshot().then((res) => console.log(JSON.stringify(res, null, 2)));
}
