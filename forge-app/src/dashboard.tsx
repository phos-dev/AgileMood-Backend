import React from 'react';
import ForgeReconciler, { Tabs, Tab, TabList, TabPanel } from '@forge/react';
import RF03Dashboard from './components/RF03Dashboard';
import RF06RegisterFeeling from './components/RF06RegisterFeeling';
import RF07Messages from './components/RF07Messages';

const App = () => (
  <Tabs id="agilemood-tabs">
    <TabList>
      <Tab>Dashboard</Tab>
      <Tab>Registrar Sentimento</Tab>
      <Tab>Mensagens</Tab>
    </TabList>
    <TabPanel>
      <RF03Dashboard />
    </TabPanel>
    <TabPanel>
      <RF06RegisterFeeling />
    </TabPanel>
    <TabPanel>
      <RF07Messages />
    </TabPanel>
  </Tabs>
);

ForgeReconciler.render(<App />);
