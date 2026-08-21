/**
 * PyWebView Bridge abstraction layer for Butler frontend.
 */

class PyWebViewBridge {
  public static isAvailable(): boolean {
    return typeof window !== 'undefined' && typeof window.pywebview !== 'undefined' && typeof window.pywebview.api !== 'undefined';
  }

  public static async callSkill<T = any>(skillName: string, actionName: string, payload: Record<string, any> = {}): Promise<T> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.call_skill(skillName, actionName, payload);
    }
    console.warn(`[Bridge Mock] callSkill: ${skillName}.${actionName}`, payload);
    return null as unknown as T;
  }

  public static async handleCommand(command: string): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.handle_command(command);
    }
    console.warn(`[Bridge Mock] handleCommand: ${command}`);
    return { success: true, mock: true };
  }

  public static async listFiles(path: string = ''): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.list_files(path);
    }
    console.warn(`[Bridge Mock] listFiles: ${path}`);
    return [];
  }

  public static async getFileBase64(path: string): Promise<string> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.get_file_base64(path);
    }
    console.warn(`[Bridge Mock] getFileBase64: ${path}`);
    return '';
  }

  public static async saveEditorContent(content: string, path: string): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.save_editor_content(content, path);
    }
    console.warn(`[Bridge Mock] saveEditorContent: ${path}`);
    return { success: true };
  }

  public static async getTimeMachineRange(startTs: number, endTs: number): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.get_time_machine_range(startTs, endTs);
    }
    console.warn(`[Bridge Mock] getTimeMachineRange: ${startTs} - ${endTs}`);
    return [];
  }

  public static async openOffice(path: string): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.open_office(path);
    }
    console.warn(`[Bridge Mock] openOffice: ${path}`);
    return { success: true };
  }

  public static async getUiSkills(): Promise<Array<{ name: string; frontend_path: string; [key: string]: any }>> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.get_ui_skills();
    }
    console.warn('[Bridge Mock] getUiSkills');
    return [];
  }

  public static async loadSkillFrontend(path: string): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.load_skill_frontend(path);
    }
    console.warn(`[Bridge Mock] loadSkillFrontend: ${path}`);
    return { success: true };
  }

  public static async submitFlashCommand(command: string): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.submit_flash_command(command);
    }
    console.warn(`[Bridge Mock] submitFlashCommand: ${command}`);
    return { success: true };
  }

  public static async hideFlash(): Promise<any> {
    if (this.isAvailable()) {
      return await window.pywebview!.api.hide_flash();
    }
    console.warn('[Bridge Mock] hideFlash');
    return { success: true };
  }
}

if (typeof window !== 'undefined') {
  (window as any).modernBridge = PyWebViewBridge;
  (window as any).PyWebViewBridge = PyWebViewBridge;
}
