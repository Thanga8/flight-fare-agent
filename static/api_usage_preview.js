(() => {
  const form = document.querySelector('form[action$="/search"]');
  if (!form) return;

  const field = (name) => form.elements.namedItem(name);
  const readInt = (name) => {
    const value = field(name).value.trim();
    return /^\d+$/.test(value) ? Number(value) : null;
  };
  const dateOrdinal = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const timestamp = Date.parse(`${value}T00:00:00Z`);
    if (!Number.isFinite(timestamp)) return null;
    const date = new Date(timestamp);
    if (date.toISOString().slice(0, 10) !== value) return null;
    return Math.floor(timestamp / 86400000);
  };
  const put = (id, text) => { document.getElementById(id).textContent = text; };
  const number = (value) => value.toLocaleString();

  function updatePreview() {
    const start = dateOrdinal(field('start_date').value);
    const end = dateOrdinal(field('end_date').value);
    const gap = readInt('nights_between_departures');
    const budget = readInt('serpapi_budget');
    const limit = readInt('combined_candidate_limit');
    if (start === null || end === null || gap === null || gap < 1 || budget === null || limit === null) {
      ['usage-preview-coverage', 'usage-preview-legs', 'usage-preview-combined',
        'usage-preview-totals', 'usage-preview-budget'].forEach((id) => put(id, 'Enter valid dates, gap, budget, and comparison limit to see the estimate.'));
      return;
    }
    const pairs = Math.max(0, end - gap - start + 1);
    const leg1Live = field('leg1_cache_mode').value === 'live';
    const leg2Live = field('leg2_cache_mode').value === 'live';
    const combinedLive = field('combined_cache_mode').value === 'live';
    const liveLegsPerPair = Number(leg1Live) + Number(leg2Live);
    const covered = liveLegsPerPair === 0 ? pairs : Math.min(pairs, Math.floor(budget / liveLegsPerPair));
    const leg1Calls = leg1Live ? covered : 0;
    const leg2Calls = leg2Live ? covered : 0;
    const exhaustiveLegCalls = pairs * liveLegsPerPair;
    const legCalls = leg1Calls + leg2Calls;
    const remaining = Math.max(0, budget - legCalls);
    const configuredCombinedMax = combinedLive ? Math.min(limit, remaining) : 0;
    const exhaustiveCombinedMax = combinedLive ? limit : 0;
    const fullCoverage = covered === pairs;

    put('usage-preview-coverage', pairs === 0
      ? 'Valid date pairs: 0. The selected window is too short for this departure gap.'
      : `Valid date pairs: ${number(pairs)}. Current budget covers ${number(covered)} pair${covered === 1 ? '' : 's'}${fullCoverage ? ' (full date coverage).' : ' (partial date coverage).'}`);
    put('usage-preview-legs', `Leg 1 live requests: ${number(leg1Calls)}${leg1Live ? '' : ' (cache-only; 0 live requests)'}. Leg 2 live requests: ${number(leg2Calls)}${leg2Live ? '' : ' (cache-only; 0 live requests)'}.`);
    if (!combinedLive || limit === 0) {
      put('usage-preview-combined', `Combined verification live requests: 0${combinedLive ? ' (candidate limit is zero).' : ' (cache-only mode).'}${combinedLive && limit === 0 ? '' : ' Cache-only misses do not trigger live calls.'}`);
    } else {
      put('usage-preview-combined', `Combined verification: up to ${number(exhaustiveCombinedMax)} additional requests for exhaustive date coverage; up to ${number(configuredCombinedMax)} within this configured search. Actual calls depend on returned candidates and remaining budget.`);
    }
    put('usage-preview-totals', `Exhaustive-search estimate: ${number(exhaustiveLegCalls)} leg requests + up to ${number(exhaustiveCombinedMax)} combined = up to ${number(exhaustiveLegCalls + exhaustiveCombinedMax)} total. Configured-search estimate: ${number(legCalls)} leg requests + up to ${number(configuredCombinedMax)} combined = up to ${number(legCalls + configuredCombinedMax)} total.`);
    const status = pairs === 0 ? 'No valid date pairs to search.' : fullCoverage
      ? 'Full date coverage appears possible within this budget.'
      : 'Partial date coverage: the current budget cannot search every valid date pair.';
    put('usage-preview-budget', `${status} Configured request budget: ${number(budget)}. Planned leg usage: ${number(legCalls)}; up to ${number(configuredCombinedMax)} combined requests; at least ${number(Math.max(0, budget - legCalls - configuredCombinedMax))} requests remain if all those calls occur. The app may use fewer requests.`);
  }

  ['start_date', 'end_date', 'nights_between_departures', 'serpapi_budget',
    'leg1_cache_mode', 'leg2_cache_mode', 'combined_candidate_limit', 'combined_cache_mode']
    .forEach((name) => field(name).addEventListener('input', updatePreview));
  form.addEventListener('change', updatePreview);
  updatePreview();
})();
