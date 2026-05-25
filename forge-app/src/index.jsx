import ForgeUI, {
  render,
  BoardPage,
  IssuePanel,
  GlobalSettings,
} from '@forge/ui';

import Settings from './components/Settings';
import RF03Dashboard from './components/RF03Dashboard';
import RF06RegisterFeeling from './components/RF06RegisterFeeling';
import RF07Messages from './components/RF07Messages';

export const runDashboard = render(
  <BoardPage>
    <RF03Dashboard />
  </BoardPage>
);

export const runRegisterFeeling = render(
  <IssuePanel>
    <RF06RegisterFeeling />
  </IssuePanel>
);

export const runMessages = render(
  <IssuePanel>
    <RF07Messages />
  </IssuePanel>
);

export const runSettings = render(
  <GlobalSettings>
    <Settings />
  </GlobalSettings>
);
