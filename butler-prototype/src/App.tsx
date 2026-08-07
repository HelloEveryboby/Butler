import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout.js';
import Dashboard from './pages/Dashboard.js';
import Clients from './pages/Clients.js';
import Playground from './pages/Playground.js';
import Tools from './pages/Tools.js';
import Usage from './pages/Usage.js';
import Logs from './pages/Logs.js';
import Settings from './pages/Settings.js';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/playground" element={<Playground />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/usage" element={<Usage />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;