import React from 'react';
import { RecoveryQueue } from './pages/RecoveryQueue';
import './index.css';

const App: React.FC = () => {
  return (
    <div className="app-layout">
      <main className="main-content">
        <RecoveryQueue />
      </main>
    </div>
  );
};

export default App;
