// 主應用元件 — 根據 currentPage 渲染對應頁面
import { Box, CssBaseline, ThemeProvider } from '@mui/material';
import { darkTheme } from './theme';
import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';
import ScriptEditor from './pages/ScriptEditor';
import AssetManager from './pages/AssetManager';
import TaskRunner from './pages/TaskRunner';
import Settings from './pages/Settings';
import { useAppStore } from './stores/appStore';
import { useEffect } from 'react';

// 頁面路由映射
const PAGE_MAP: Record<string, React.FC> = {
  dashboard: Dashboard,
  scripts: ScriptEditor,
  assets: AssetManager,
  runner: TaskRunner,
  settings: Settings,
};

const App = () => {
  const { currentPage, fetchScripts, fetchAssets } = useAppStore();

  // 初始化時載入資料
  useEffect(() => {
    fetchScripts();
    fetchAssets();
  }, [fetchScripts, fetchAssets]);

  const PageComponent = PAGE_MAP[currentPage] ?? Dashboard;

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
        <Sidebar />
        <Box sx={{ flex: 1, overflow: 'hidden' }}>
          <PageComponent />
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;
