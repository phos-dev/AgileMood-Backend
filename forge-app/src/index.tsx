import * as ForgeUI from 'react';
import ForgeReconciler from '@forge/react';
import RF03Dashboard from './components/RF03Dashboard';
import RF06RegisterFeeling from './components/RF06RegisterFeeling';
import RF07Messages from './components/RF07Messages';
import Settings from './components/Settings';

export const runDashboard = () => ForgeReconciler.render(<RF03Dashboard />);
export const runRegisterFeeling = () => ForgeReconciler.render(<RF06RegisterFeeling />);
export const runMessages = () => ForgeReconciler.render(<RF07Messages />);
export const runSettings = () => ForgeReconciler.render(<Settings />);
