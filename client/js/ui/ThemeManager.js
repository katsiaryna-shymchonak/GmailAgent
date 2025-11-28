/**
 * Theme Manager
 */
export class ThemeManager {
  constructor(themeBtn) {
    this.themeBtn = themeBtn;
    this.init();
  }

  init() {
    const theme =
      localStorage.getItem('gmail_agent_theme') ||
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light'
        : 'dark');
    this.applyTheme(theme);
    this.setupListener();
  }

  setupListener() {
    this.themeBtn.addEventListener('click', () => {
      const isLight = document.body.classList.contains('light');
      const newTheme = isLight ? 'dark' : 'light';
      localStorage.setItem('gmail_agent_theme', newTheme);
      this.applyTheme(newTheme);
      this.themeBtn.setAttribute('aria-label', `Switch to ${isLight ? 'light' : 'dark'} mode`);
    });
  }

  applyTheme(theme) {
    if (theme === 'light') {
      document.body.classList.add('light');
      this.themeBtn.textContent = '🌞';
      this.themeBtn.title = 'Switch to dark mode';
    } else {
      document.body.classList.remove('light');
      this.themeBtn.textContent = '🌙';
      this.themeBtn.title = 'Switch to light mode';
    }
  }
}
