import React, { useState, useEffect } from 'react';
import ForgeReconciler, { Text, Tabs, Tab, TabList, TabPanel } from '@forge/react';
import { invoke } from '@forge/bridge';
import RF03Dashboard from './components/RF03Dashboard';
import RF06RegisterFeeling from './components/RF06RegisterFeeling';
import RF07Messages from './components/RF07Messages';
import Settings from './components/Settings';

const App = () => {
  const [settings, setSettings] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);

  const reload = () =>
    invoke<any>('getSettings').then((s: any) => {
      setSettings(s);
      setLoaded(true);
    });

  useEffect(() => { reload(); }, []);

  if (!loaded) return <Text>Carregando...</Text>;

  const role = settings?.role;

  return (
    <Tabs id="agilemood-tabs">
      <TabList>
        {role === 'manager' && <Tab>Dashboard</Tab>}
        {role === 'employee' && <Tab>Registrar Sentimento</Tab>}
        {role === 'employee' && <Tab>Mensagens</Tab>}
        <Tab>Configurações</Tab>
      </TabList>
      {role === 'manager' && <TabPanel><RF03Dashboard /></TabPanel>}
      {role === 'employee' && <TabPanel><RF06RegisterFeeling /></TabPanel>}
      {role === 'employee' && <TabPanel><RF07Messages /></TabPanel>}
      <TabPanel><Settings onLogin={reload} /></TabPanel>
    </Tabs>
  );
};

ForgeReconciler.render(<App />);
