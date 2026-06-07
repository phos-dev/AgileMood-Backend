import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  Range as RawRange,
  DynamicTable as RawDynamicTable,
  Lozenge as RawLozenge,
  Box as RawBox,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const Range = RawRange as any;
const DynamicTable = RawDynamicTable as any;
const Lozenge = RawLozenge as any;
const Box = RawBox as any;
import { invoke } from '@forge/bridge';

const QUESTIONS = [
  'Se você comete um erro neste time, muitas vezes ele é usado contra você.',
  'Os membros deste time são capazes de levantar problemas e questões difíceis.',
  'As pessoas neste time às vezes rejeitam outras por serem diferentes.',
  'É seguro arriscar neste time.',
  'É difícil pedir ajuda a outros membros deste time.',
  'Nenhum membro deste time agiria de forma a prejudicar deliberadamente os esforços dos outros.',
  'Minhas habilidades únicas e talentos são valorizados e utilizados neste time.',
];


const PS_REPORT_HEAD = {
  cells: [
    { key: 'sprint', content: 'Sprint' },
    { key: 'responses', content: 'Respostas' },
    { key: 'mean', content: 'Média (1–5)' },
    { key: 'status', content: 'Status' },
    { key: 'std', content: 'Desvio padrão' },
  ],
};

function psLozenge(mean: number) {
  if (mean >= 4) return <Lozenge appearance="success">Bom</Lozenge>;
  if (mean >= 3) return <Lozenge appearance="moved">Moderado</Lozenge>;
  return <Lozenge appearance="removed">Atenção</Lozenge>;
}

export default function RF01PsQuestionnaire() {
  const [settings, setSettings] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);
  const [sprintState, setSprintState] = useState<any>(null);
  const [sprintLoaded, setSprintLoaded] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({
    q1: 3, q2: 3, q3: 3, q4: 3, q5: 3, q6: 3, q7: 3,
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
      setSettings(s);
      setLoaded(true);
      if (!s?.jwtToken || !s?.teamId) { setSprintLoaded(true); return; }

      if (s.role === 'manager') {
        invoke<any>('getPsReport', { teamId: s.teamId, jwtToken: s.jwtToken })
          .then((r: any) => { setReport(r); setSprintLoaded(true); })
          .catch(() => { setReport({ scores: [] }); setSprintLoaded(true); });
      } else {
        invoke<any>('getSprintToken', { teamId: s.teamId, jwtToken: s.jwtToken })
          .then((state: any) => { setSprintState(state); setSprintLoaded(true); })
          .catch(() => { setSprintState({ status: 'no_active_sprint' }); setSprintLoaded(true); });
      }
    });
  }, []);

  if (!loaded) return <Text>Carregando...</Text>;

  if (!settings?.jwtToken) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning" actions={[]} testId="sm-cfg">
        <Text>Faça login na aba Configurações.</Text>
      </SectionMessage>
    );
  }

  if (!settings?.teamId) {
    return (
      <SectionMessage title="Equipe não configurada" appearance="warning" actions={[]} testId="sm-noteam">
        <Text>Sua conta não está associada a uma equipe. Verifique no AgileMood.</Text>
      </SectionMessage>
    );
  }

  if (!sprintLoaded) return <Text>Carregando...</Text>;

  if (settings.role === 'manager') {
    const scores = report?.scores ?? [];
    return (
      <Stack space="space.200">
        <Text><Strong>Segurança Psicológica — Histórico por Sprint</Strong></Text>
        <Text>Pontuação de 1 a 5 · itens reversos já ajustados · médias anônimas do time.</Text>
        {scores.length === 0 ? (
          <SectionMessage title="Sem dados ainda" appearance="information" actions={[]} testId="sm-empty">
            <Text>Nenhuma resposta registrada. O questionário é enviado automaticamente ao time quando um sprint é encerrado.</Text>
          </SectionMessage>
        ) : (
          <DynamicTable
            head={PS_REPORT_HEAD}
            rows={scores.map((s: any) => ({
              key: `sprint-${s.sprint_number}`,
              cells: [
                { key: 'sprint', content: s.sprint_name ?? `Sprint ${s.sprint_number}` },
                { key: 'responses', content: String(s.response_count) },
                { key: 'mean', content: s.mean_score.toFixed(2) },
                { key: 'status', content: psLozenge(s.mean_score) },
                { key: 'std', content: s.std_dev.toFixed(2) },
              ],
            }))}
          />
        )}
        {scores.length > 0 && (
          <Stack space="space.100">
            <Text><Strong>Como interpretar</Strong></Text>
            <Text>Média ≥ 4 — time saudável, alto índice de segurança psicológica.</Text>
            <Text>Média entre 3 e 4 — nível moderado. Monitore a tendência nos próximos sprints.</Text>
            <Text>Média &lt; 3 — sinal de alerta. O time pode não se sentir seguro para arriscar, discordar ou pedir ajuda. Considere uma retrospectiva focada em segurança psicológica.</Text>
            <Text>Desvio padrão &gt; 1 — o time está dividido: alguns se sentem seguros, outros não. Pode indicar subgrupos ou relações específicas problemáticas.</Text>
            <Text>Tendência entre sprints — média subindo indica que intervenções estão funcionando; média caindo indica que algo aconteceu no time.</Text>
          </Stack>
        )}
      </Stack>
    );
  }

  if (sprintState?.status === 'session_expired') {
    return (
      <SectionMessage title="Sessão expirada. Desconecte e reconecte nas Configurações." appearance="error" actions={[]} testId="sm-session">
        <Text> </Text>
      </SectionMessage>
    );
  }

  if (sprintState?.status === 'no_active_sprint') {
    return (
      <SectionMessage title="Nenhum sprint ativo" appearance="information" actions={[]} testId="sm-nosprint">
        <Text>Nenhum sprint ativo no momento. O questionário fica disponível por 48h após o encerramento do sprint.</Text>
      </SectionMessage>
    );
  }

  if (sprintState?.status === 'expired') {
    return (
      <SectionMessage title="Questionário expirado" appearance="error" actions={[]} testId="sm-expired">
        <Text>O prazo para responder este questionário encerrou. Fale com o Scrum Master.</Text>
      </SectionMessage>
    );
  }

  if (sprintState?.status === 'answered' || submitted) {
    const answeredAt = sprintState?.answered_at
      ? new Date(sprintState.answered_at).toLocaleDateString('pt-BR')
      : null;
    return (
      <SectionMessage title="Obrigado pela sua resposta!" appearance="confirmation" actions={[]} testId="sm-done">
        <Text>
          {answeredAt
            ? `Você respondeu em ${answeredAt}. Sua resposta foi registrada anonimamente.`
            : 'Sua resposta foi registrada anonimamente.'}
        </Text>
      </SectionMessage>
    );
  }

  const handleSubmit = async () => {
    setError(null);
    try {
      await invoke('submitPsQuestionnaire', {
        jwtToken: settings.jwtToken,
        sprint_token: sprintState.sprint_token,
        answers,
      });
      setSubmitted(true);
    } catch (e: any) {
      if (e.message?.includes('401')) {
        setError('Sessão expirada. Reconecte nas Configurações.');
      } else if (e.message?.includes('409')) {
        setError('Você já respondeu este questionário.');
      } else {
        setError(`Erro ao enviar: ${e.message}`);
      }
    }
  };

  return (
    <Stack space="space.200">
      <Text><Strong>Questionário de Segurança Psicológica — {sprintState?.sprint_name ?? `Sprint ${sprintState?.sprint_number}`}</Strong></Text>
      <SectionMessage title="Respostas anônimas" appearance="information" actions={[]} testId="sm-anon">
        <Text>Suas respostas não são associadas ao seu nome. O gestor vê apenas médias do time.</Text>
      </SectionMessage>
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
          <Text> </Text>
        </SectionMessage>
      )}
      {QUESTIONS.map((question, idx) => {
        const key = `q${idx + 1}`;
        return (
          <React.Fragment key={key}>
            <Stack space="space.100">
              <Text>{idx + 1}. {question}</Text>
              <Text>1 — Discordo totalmente &nbsp;·&nbsp; 5 — Concordo totalmente</Text>
              <Range
                name={key}
                min={1}
                max={5}
                step={1}
                value={answers[key]}
                onChange={(v: number) => setAnswers((prev) => ({ ...prev, [key]: v }))}
              />
              <Text>Resposta: <Strong>{answers[key]}</Strong></Text>
            </Stack>
            {idx < QUESTIONS.length - 1 && (
              <Box backgroundColor="color.border" paddingBlock="space.025" />
            )}
          </React.Fragment>
        );
      })}
      <Button type="button" onClick={handleSubmit}>Enviar respostas</Button>
    </Stack>
  );
}
