/**
 * PyWebView API TypeScript Interface Definitions
 */

export interface PyWebViewAPI {
  handle_command(command: string): Promise<any>;
  call_skill(skillName: string, actionName: string, payload?: Record<string, any>): Promise<any>;
  list_files(path?: string): Promise<any>;
  get_file_base64(path: string): Promise<string>;
  save_editor_content(content: string, path: string): Promise<any>;
  get_time_machine_range(startTs: number, endTs: number): Promise<any>;
  open_office(path: string): Promise<any>;
  get_ui_skills(): Promise<Array<{ name: string; frontend_path: string; [key: string]: any }>>;
  load_skill_frontend(path: string): Promise<any>;
  submit_flash_command(command: string): Promise<any>;
  hide_flash(): Promise<any>;
  unlock_vault?(pwd: string): Promise<boolean>;
  set_voice_engine?(mode: string): Promise<boolean>;
  get_input_suggestions?(prefix: string): Promise<string[]>;
}

export interface PyWebView {
  api: PyWebViewAPI;
}

declare global {
  interface Window {
    pywebview?: PyWebView;
  }
}
