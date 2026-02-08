import { create } from 'zustand';

interface AppState {
  /** 首页品牌重塑提示是否已关闭 */
  bannerDismissed: boolean;
  setBannerDismissed: (v: boolean) => void;
  /** 详情页当前选中的文件路径（用于右侧编辑器） */
  selectedFilePath: string | null;
  setSelectedFilePath: (path: string | null) => void;
  initialPrompt: string;
  setInitialPrompt: (prompt: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  bannerDismissed: false,
  setBannerDismissed: (v) => set({ bannerDismissed: v }),
  selectedFilePath: null,
  setSelectedFilePath: (path) => set({ selectedFilePath: path }),
  initialPrompt: '',
  setInitialPrompt: (prompt) => set({ initialPrompt: prompt }),
}));
