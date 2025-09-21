<script lang="ts">
  import { onMount } from 'svelte';

  // ---------------- Types ----------------
  type Task = { id: string; type: 'highlight' | 'short' | 'vocab'; prompt: string; done?: boolean; answer?: string };
  type Evidence = { id: string; text: string; start: number; end: number };
  type StudentRow = {
  name: string;
  time: string;
  tasks: string;
  quality: 'Strong' | 'Medium' | 'Weak';
  flags?: string;
  flagsDemo?: boolean;
  score?: number;
  rubric?: {
    completeness: number;
    evidence: number;
    relevance: number;
    fluency: number;
    levelAdjust: number;
    total: number;
  };
  feedback?: string;
};

  // --------------- State -----------------
  let screen: 'student' | 'teacher' = 'student';
  let title = 'Colonial Rationing Case Study';
  let reading = `The colony faced dwindling grain reserves after a failed harvest. Councils debated rationing policy. Merchants argued for price ceilings while officials proposed equitable distribution based on household size. Diaries from the period reveal mixed reactions among townspeople, noting both relief and resentment. Implementation of ration books began the following month. Bakers received flour allocations tied to reported demand. Rumors of favoritism spread, particularly concerning officials and their associates. Audits later contradicted some claims.

Historians point out that rationing systems are often perceived as unfair in the short term but can stabilize markets. The language of official notices emphasized civic duty and mutual sacrifice, while diaries reveal anxiety over scarcity and social standing.`;

  let tasks: Task[] = [
    { id: 't1', type: 'highlight', prompt: 'Highlight the sentence where the author explains why rationing was necessary.' },
    { id: 't2', type: 'short', prompt: 'Summarize paragraph 2 in your own words (1–2 sentences).' },
    { id: 't3', type: 'vocab', prompt: 'Define the term “ration”.' }
  ];

  let evidence: Evidence[] = [];
  let dwellMs = 0;
  let timer: any;
  onMount(() => { timer = setInterval(() => (dwellMs += 1000), 1000); });
  function destroy() { clearInterval(timer); }

  function percentDone() { return Math.round((tasks.filter((t) => t.done).length / tasks.length) * 100); }

  // ---------- LLM-style grading mock (uses reading context, simulates model output) ----------
function gradeRowLLM(r: StudentRow) {
  const baseline = r.quality === 'Strong' ? 0.8 : r.quality === 'Medium' ? 0.6 : 0.4;

  // Simulated answer based on row.quality (stand-in for real student answer)
  const sampleAnswer =
    r.quality === 'Strong'
      ? 'Rationing was necessary due to failed harvest and scarce supplies.'
      : r.quality === 'Medium'
      ? 'They made ration books to be fair.'
      : 'It was about food.';

  // Compare answer to the real passage
  const relevance = jaccard(reading, sampleAnswer);   // 0–1 similarity
  const fluency   = fluencyProxy(sampleAnswer);        // 0–1 proxy
  const evidence  = r.quality !== 'Weak' ? 0.7 : 0.3;  // pretend highlight/interaction
  const completeness = baseline;                       // coverage proxy
  const levelAdjust  = r.quality === 'Weak' ? 0.05 : r.quality === 'Strong' ? -0.02 : 0.0;

  const total = Math.max(
    0,
    Math.min(
      1,
      0.25 * completeness +
      0.30 * relevance +
      0.25 * evidence +
      0.20 * fluency +
      levelAdjust
    )
  );

  r.rubric = { completeness, evidence, relevance, fluency, levelAdjust, total };
  r.score  = Math.round(total * 100);
  r.feedback =
    total > 0.85
      ? 'Strong, on-topic, fluent. Consider citing a specific policy detail from the passage for full credit.'
      : total > 0.65
      ? 'Mostly correct. Clarify the rationale for rationing (failed harvest, scarcity) and reference a quoted sentence.'
      : 'Off-target or incomplete. Re-read the first paragraph and identify why rationing began; include a short quote as evidence.';
  return r;
}

function gradeAllLLM() {
  rows = rows.map(gradeRowLLM);
}


  function onMouseUpCapture() {
    const selection = window.getSelection?.();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    const container = document.getElementById('reading')!;
    if (!container.contains(range.commonAncestorContainer)) return;
    const text = selection.toString();
    if (!text || text.trim().length < 3) return;

    // Compute offsets (simple mock)
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let acc = 0, startGlobal = -1, endGlobal = -1;
    while (walker.nextNode()) {
      const node = walker.currentNode as Text;
      if (node === range.startContainer) startGlobal = acc + range.startOffset;
      if (node === range.endContainer) { endGlobal = acc + range.endOffset; break; }
      acc += node.nodeValue?.length || 0;
    }
    if (startGlobal >= 0 && endGlobal > startGlobal) {
      evidence = [...evidence, { id: 'e' + (evidence.length + 1), text, start: startGlobal, end: endGlobal }];
      const ht = tasks.find((t) => t.type === 'highlight');
      if (ht) ht.done = true;
    }
    selection.removeAllRanges();
  }

  function setAnswer(id: string, val: string) {
    const t = tasks.find((x) => x.id === id);
    if (!t) return;
    t.answer = val;
    t.done = (val || '').trim().length > 3;
  }

  // ---------- Teacher data ----------
  let rows: StudentRow[] = [
    { name: 'Alice W.', time: '15m', tasks: '7/7', quality: 'Strong' },
    { name: 'Ben R.', time: '9m', tasks: '5/7', quality: 'Weak' },
    { name: 'Chris T.', time: '14m', tasks: '6/7', quality: 'Medium' }
  ];
  let selected: StudentRow | null = null;
  function openStudent(r: StudentRow) { selected = r; }
  function closeStudent() { selected = null; }

  // -------- Premium & Skim controls --------
  let featureFlags = { premium: false };
  let skimEnabled: boolean = false; // UI toggle (only meaningful if premium)
  let skimThresh = { minDwellMs: 8000, minInteractions: 1, graceRatio: 0.3 };

  // Reactive: auto-seed a DEMO flag when Premium+Skim enabled and no flags exist
  $: if (featureFlags.premium && skimEnabled) {
    if (!rows.some(r => r.flags)) {
      rows = rows.map(r => r.name === 'Ben R.' ? { ...r, flags: 'Possible skim', flagsDemo: true } : r);
    }
  }

  // Reactive: auto-clear only DEMO flags when Skim disabled or Premium off
  $: if (!featureFlags.premium || !skimEnabled) {
    if (rows.some(r => r.flagsDemo)) {
      rows = rows.map(r => r.flagsDemo ? ({ ...r, flags: undefined, flagsDemo: undefined }) : r);
    }
  }

  // DEV helpers: seed/clear REAL flags (persist regardless of premium/skim toggles)
  function seedRealFlag(name: string, label = 'Skim (real)') {
    rows = rows.map(r => r.name === name ? ({ ...r, flags: label, flagsDemo: false }) : r);
  }
  function clearRealFlags() {
    rows = rows.map(r => r.flagsDemo ? r : ({ ...r, flags: undefined }));
  }

  // overlay keyboard accessibility
  function overlayKey(e: KeyboardEvent) {
    if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
      closeStudent();
    }
  }

// ---------- Rule-based rubric scoring (demo) ----------
function tokenize(s: string) {
  return (s || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(Boolean);
}
function jaccard(a: string, b: string) {
  const A = new Set(tokenize(a));
  const B = new Set(tokenize(b));
  const inter = [...A].filter(x => B.has(x)).length;
  const union = new Set([...A, ...B]).size || 1;
  return inter / union; // 0–1
}
function fluencyProxy(ans: string) {
  const len = (ans || '').length;
  const sentences = (ans.match(/[.!?]/g) || []).length || 1;
  return Math.min(1, (len / 200) * (sentences / 2)); // crude 0–1
}

// Map quality -> baseline, then adjust using similarity to reading
function gradeRow(r: StudentRow) {
  // In a real app, we'd grade per-question. For demo, derive from row.quality and reading overlap.
  const baseline = r.quality === 'Strong' ? 0.8 : r.quality === 'Medium' ? 0.6 : 0.4;
  const sampleAnswer =
    r.quality === 'Strong'
      ? 'Rationing was necessary due to failed harvest and scarce supplies.'
      : r.quality === 'Medium'
      ? 'They made ration books to be fair.'
      : 'It was about food.';

  const relevance = jaccard(reading, sampleAnswer); // 0–1 vs. the actual reading text
  const fluency = fluencyProxy(sampleAnswer);       // 0–1
  const evidence = r.quality !== 'Weak' ? 0.7 : 0.3; // pretend highlight/interaction
  const completeness = baseline;                      // coverage proxy
  const flagPenalty = r.flags ? 0.1 : 0;
  const levelAdjust = 0; // hook: adjust +/- based on student level
  const total = Math.max(
    0,
    Math.min(
      1,
      0.25 * completeness + 0.30 * relevance + 0.25 * evidence + 0.20 * fluency - flagPenalty + levelAdjust
    )
  );

  r.rubric = { completeness, evidence, relevance, fluency, levelAdjust, total };
  r.score = Math.round(total * 100);
  return r;
}

function gradeAll() {
  rows = rows.map(gradeRow);
}

</script>

<style>
  /* Use :global for truly global selectors inside a component */
  :global(body) { background: #0b1020; color: #e6e9ef; margin: 0; }

  .wrap { padding: 24px; max-width: 1200px; margin: 0 auto; }
  .card { background: #0f1428; border-radius: 16px; padding: 16px; }
  .grid { display:grid; gap:16px; }
  .two { grid-template-columns: 1fr 360px; }
  .title { font-size: 1.25rem; font-weight: 700; }
  .muted { color: #9aa3b2; }
  .btn { background: #7c9cff; color:#0b1020; border:none; padding:10px 14px; border-radius:10px; font-weight:700; cursor:pointer; }
  .btn.secondary { background: rgba(255,255,255,.08); color: #e6e9ef; }
  .pill { display:inline-block; padding: 2px 8px; border-radius:999px; background: rgba(255,255,255,.06); font-size:12px; }
  .table { width:100%; border-collapse: collapse; }
  .table th, .table td { border-bottom: 1px solid rgba(255,255,255,0.1); padding: 8px; text-align: left; }
  .right { display:flex; align-items:center; justify-content:flex-end; gap: 8px; flex-wrap: wrap; }
  .drawer { max-height: calc(100vh - 64px); overflow:auto; position: sticky; top: 24px; }
  .hl { background: rgba(124,156,255,.18); border-left: 3px solid #7c9cff; padding: 8px; border-radius: 8px; margin: 8px 0; }
  .progress { height: 10px; background: rgba(255,255,255,.08); border-radius: 999px; overflow: hidden; }
  .bar { height: 100%; background: #3ddc97; width: 0%; transition: width .3s ease; }
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display:flex; align-items:center; justify-content:center; }
  .modal { width: 900px; max-width: 95vw; }
</style>

<div class="wrap">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
    <div class="title">Proof‑of‑Reading LMS (Wireframes)</div>

    <div class="right">
      <button class="btn secondary" on:click={gradeAll}>DEV: Grade All (rule-based)</button>
      <button class="btn secondary" on:click={() => screen='student'}>Student View</button>
      <button class="btn" on:click={() => screen='teacher'}>Teacher Dashboard</button>
    </div>
  </div>
  <button class="btn secondary" on:click={gradeAllLLM}>DEV: Grade All (LLM mock)</button>


  {#if screen==='student'}
    <!-- Student: Interactive Reader -->
    <div class="grid two">
      <main class="card">
        <div class="title" style="margin-bottom:4px;">{title}</div>
        <div class="muted" style="margin-bottom:12px;">Read naturally; complete tasks as you go. Highlights count as evidence.</div>

        <!-- attach the selection handler here (accessible) -->
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <div
          id="reading"
          style="line-height:1.9; white-space:pre-wrap;"
          on:mouseup|capture={onMouseUpCapture}
          role="region"
          aria-label="Reading content"
        >
          {reading}
        </div>

        <div style="margin-top:16px;">
          <div class="muted" style="margin-bottom:6px;">Your evidence</div>
          {#if evidence.length===0}
            <div class="muted">No highlights yet. Drag to select a sentence.</div>
          {:else}
            {#each evidence as ev}
              <div class="hl">“{ev.text}” <span class="pill">{ev.start}–{ev.end}</span></div>
            {/each}
          {/if}
        </div>
      </main>

      <aside class="card drawer" aria-label="Tasks panel">
        <div class="title" style="margin-bottom:8px;">Tasks</div>
        <div class="muted" style="margin-bottom:8px;">Progress</div>
        <div class="progress"><div class="bar" style={`width:${percentDone()}%`}></div></div>
        <div class="muted" style="margin:8px 0 16px 0;">{tasks.filter(t=>t.done).length}/{tasks.length} completed • {Math.floor(dwellMs/60_000)}m spent</div>

        <!-- Task list -->
        {#each tasks as t}
          <div class="card" style="margin-bottom:10px;">
            <div style="font-weight:600;">{t.prompt}</div>
            {#if t.type==='highlight'}
              <div class="muted" style="font-size:12px;">Select a sentence in the reading to complete.</div>
              {#if t.done}<div class="pill" style="margin-top:6px;background:rgba(61,220,151,.18); color: #3ddc97;">Completed</div>{/if}
            {:else}
              <textarea class="card" rows="3" placeholder="Type your response…" on:input={(e:any)=> setAnswer(t.id, e.target.value)}>{t.answer || ''}</textarea>
            {/if}
          </div>
        {/each}

        <button class="btn" style="width:100%; margin-top:8px;">Submit All Evidence & Answers</button>
      </aside>
    </div>
  {/if}

  {#if screen==='teacher'}
    <!-- Premium Settings (Skim Alerts) -->
    {#if featureFlags.premium}
      <section class="card" style="margin-bottom:16px;">
        <div class="title">Premium • Skim Alerts</div>
        <label style="display:flex;align-items:center;gap:8px;margin:8px 0;">
          <input type="checkbox" bind:checked={skimEnabled} />
          Enable skim alerts (time-on-section + few interactions)
        </label>
        {#if skimEnabled}
          <div style="display:flex; gap:12px;">
            <label style="flex:1">Min dwell per bin (ms)
              <input class="btn secondary" type="number" min="0" bind:value={skimThresh.minDwellMs} />
            </label>
            <label style="flex:1">Min interactions per bin
              <input class="btn secondary" type="number" min="0" bind:value={skimThresh.minInteractions} />
            </label>
            <label style="flex:1">Grace ratio (0–1)
              <input class="btn secondary" type="number" min="0" max="1" step="0.05" bind:value={skimThresh.graceRatio} />
            </label>
          </div>
          <div class="muted" style="margin-top:6px;font-size:12px;">We never block submissions. Alerts are suggestions for teacher review only.</div>
        {/if}
      </section>
    {:else}
      <section class="card" style="margin-bottom:16px;">
        <div class="title">Skim Alerts</div>
        <div class="muted">Flag possible skimming using low time-on-section and missing evidence.</div>
        <div class="muted" style="margin-top:6px;">Unlock with Premium to configure thresholds and see alerts.</div>
      </section>
    {/if}

    <!-- Teacher: Evidence Map -->
    <section class="grid" style="grid-template-columns: repeat(4, 1fr);">
      <div class="card">
        <div class="muted">Submissions</div>
        <div class="title">28<span class="muted">/30</span></div>
      </div>
      <div class="card">
        <div class="muted">Avg dwell</div>
        <div class="title">14m</div>
      </div>
      <div class="card">
        <div class="muted">Avg completion</div>
        <div class="title">6.8<span class="muted">/7</span></div>
      </div>
      <div class="card">
        <div class="muted">Flags</div>
        <div class="title">{rows.filter(r=>r.flags).length} <span class="muted">skim alerts</span></div>
      </div>
    </section>

    <section class="card" style="margin-top:16px;">
      <div class="title" style="margin-bottom:8px;">Student Evidence Table</div>
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Time</th><th>Tasks Done</th><th>Evidence Quality</th><th>Score</th><th>Flags</th><th></th></tr>
        </thead>
        <tbody>
          {#each rows as r}
            <tr>
              <td>{r.name}</td>
              <td>{r.time}</td>
              <td>{r.tasks}</td>
              <td>{r.quality}</td>
              <td>{r.score != null ? r.score + '%' : '—'}</td>
              <td>
                {#if r.flags}
                  <span class="pill" style="background:rgba(255,209,102,.18); color: #ffd166;" title="Possible skim: flagged when dwell time and interactions fall below thresholds. Click to review details.">{r.flags}{r.flagsDemo ? ' (demo)' : ''}</span>
                {:else}
                  —
                {/if}
              </td>
              <td><button class="btn secondary" on:click={() => openStudent(r)}>View</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
      <div class="muted" style="margin-top:8px;font-size:12px;">
        {#if featureFlags.premium && skimEnabled}
          <span class="pill" style="background:rgba(255,209,102,.18); color: #ffd166;">Possible skim</span> = flagged when dwell time and interactions fall below thresholds. Demo flags auto-clear; real flags persist.
        {/if}
        {#if selected && selected.rubric}
          <div style="margin-top:8px;">
            <div>Rubric: completeness {selected.rubric.completeness.toFixed(2)}, evidence {selected.rubric.evidence.toFixed(2)}, relevance {selected.rubric.relevance.toFixed(2)}, fluency {selected.rubric.fluency.toFixed(2)}, total {(selected.rubric.total*100).toFixed(0)}%</div>
          </div>
        {/if}
      </div>
    </section>

    {#if selected}
      <!-- Make overlay keyboard-accessible -->
      <div
        class="overlay"
        role="button"
        tabindex="0"
        aria-label="Close student drilldown"
        on:click={closeStudent}
        on:keydown={overlayKey}
      >
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <div class="card modal" on:click|stopPropagation>
          <div style="display:flex;align-items:center;justify-content:space-between; margin-bottom:8px;">
            <div class="title">{selected.name} — Evidence Drilldown</div>
            <button class="btn secondary" on:click={closeStudent}>Close</button>
          </div>

          <div class="grid two">
            <div class="card">
              <div class="muted" style="margin-bottom:8px;">Reading with highlights (mock)</div>
              <div class="hl">“failed harvest … rationing policy” <span class="pill">evidence</span></div>
              <div class="hl">“Rumors of favoritism … audits later contradicted” <span class="pill">evidence</span></div>
            </div>

            <div class="card">
              <div class="muted">Submitted answers</div>
              <div class="card" style="margin-top:8px;">
                <div style="font-weight:600;">Q1</div>
                <div class="muted">Short answer: “Because the harvest failed and supplies ran low.”</div>
              </div>
              <div class="card" style="margin-top:8px;">
                <div style="font-weight:600;">Q2</div>
                <div class="muted">Summary: “The policy aimed to allocate flour fairly, though people feared favoritism.”</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    {/if}
  {/if}
</div>
