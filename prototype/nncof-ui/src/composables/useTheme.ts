// 애플리케이션의 다크·라이트 테마 상태를 관리하는 컴포저블
import { readonly, ref } from 'vue';

export type Theme = 'dark' | 'light';

const THEME_STORAGE_KEY = 'ncof-theme';
const theme = ref<Theme>('dark');
let initialized = false;

const getInitialTheme = (): Theme => {
  try {
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === 'dark' || savedTheme === 'light') {
      return savedTheme;
    }
  } catch {
    // 저장소를 사용할 수 없는 환경에서는 시스템 설정을 사용한다.
  }

  if (window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }

  return 'dark';
};

const applyTheme = (nextTheme: Theme) => {
  document.documentElement.dataset.theme = nextTheme;
  document.documentElement.style.colorScheme = nextTheme;
};

export const initializeTheme = () => {
  if (initialized) return;

  theme.value = getInitialTheme();
  applyTheme(theme.value);
  initialized = true;
};

const setTheme = (nextTheme: Theme) => {
  theme.value = nextTheme;
  applyTheme(nextTheme);

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  } catch {
    // 저장에 실패해도 현재 세션의 테마 전환은 유지한다.
  }
};

const toggleTheme = () => {
  setTheme(theme.value === 'dark' ? 'light' : 'dark');
};

export const useTheme = () => {
  initializeTheme();

  return {
    theme: readonly(theme),
    setTheme,
    toggleTheme,
  };
};
