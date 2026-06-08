import React, { useState, useEffect } from 'react';
import ForgeReconciler, { Text, Tabs, Tab, TabList, TabPanel, Box } from '@forge/react';
import { invoke } from '@forge/bridge';
import RF01PsQuestionnaire from './components/RF01PsQuestionnaire';
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
        {role === 'manager' && <Tab>Dashboard - Humor da Equipe</Tab>}
        {role === 'employee' && <Tab>Registrar Sentimento</Tab>}
        {role === 'employee' && <Tab>Mensagens Recebidas</Tab>}
        {settings?.jwtToken && <Tab>Segurança Psicológica</Tab>}
        <Tab>Configurações</Tab>
      </TabList>
      
      {role === 'manager' && (
        <TabPanel>
          <Box paddingBlockStart="space.200">
            <RF03Dashboard />
          </Box>
        </TabPanel>
      )}
      
      {role === 'employee' && (
        <TabPanel>
          <Box paddingBlockStart="space.200">
            <RF06RegisterFeeling />
          </Box>
        </TabPanel>
      )}
      
      {role === 'employee' && (
        <TabPanel>
          <Box paddingBlockStart="space.200">
            <RF07Messages />
          </Box>
        </TabPanel>
      )}
      
      {settings?.jwtToken && (
        <TabPanel>
          <Box paddingBlockStart="space.200">
            <RF01PsQuestionnaire />
          </Box>
        </TabPanel>
      )}
      
      <TabPanel>
        <Box paddingBlockStart="space.200">
          <Settings onLogin={reload} />
        </Box>
      </TabPanel>
    </Tabs>
  );
};

ForgeReconciler.render(<App />);
