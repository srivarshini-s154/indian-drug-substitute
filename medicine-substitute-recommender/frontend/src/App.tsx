
import React, { useState, useEffect } from 'react';
import HeroWave from './components/ui/dynamic-wave-canvas-background';
import {
  Pill,
  Search,
  Bot,
  Send,
  AlertTriangle,
  TrendingDown,
  ChevronDown,
  ChevronUp,
  Building2,
  ShieldCheck,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

interface QueryDrug {
  name: string;
  manufacturer: string;
  price_inr: number;
  pack_size: string;
  price_per_unit: number;
  composition: string;
  dosage_form: string;
  side_effects: string;
}

interface SideEffectComparison {
  status: 'compared' | 'insufficient_data';
  shared_effects: string[];
  substitute_only_in_data: string[];
  original_only_in_data: string[];
  message: string;
}

interface Substitute {
  rank: number;
  name: string;
  manufacturer: string;
  price_inr: number;
  pack_size: string;
  price_per_unit: number;
  savings_pct: number;
  side_effects: string;
  side_effect_similarity_pct: number;
  bayesian_rating: number;
  composite_score: number;
  side_effect_comparison?: SideEffectComparison;
}

interface RecommendationResponse {
  query_drug: QueryDrug;
  substitutes: Substitute[];
}

interface ChatMessage {
  sender: 'bot' | 'user';
  text: string;
}

type SortOption = 'savings' | 'price' | 'rating';

export default function App() {
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [queryResult, setQueryResult] =
    useState<RecommendationResponse | null>(null);

  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<SortOption>('savings');

  const [meanSavings, setMeanSavings] = useState<string>('--%');
  const [ciSavings, setCiSavings] = useState<string>('--');

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      sender: 'bot',
      text: 'Hello. Search for a medicine above to analyze substitutes and compare pricing listings.',
    },
  ]);

  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // Sort substitutes without modifying the original API response.
  const sortedSubstitutes = [...(queryResult?.substitutes ?? [])].sort(
    (a, b) => {
      switch (sortBy) {
        case 'savings':
          return (
            (Number(b.savings_pct) || 0) -
            (Number(a.savings_pct) || 0)
          );

        case 'price':
          return (
            (Number(a.price_per_unit) || 0) -
            (Number(b.price_per_unit) || 0)
          );

        case 'rating':
          return (
            (Number(b.bayesian_rating) || 0) -
            (Number(a.bayesian_rating) || 0)
          );

        default:
          return 0;
      }
    }
  );

  // Autocomplete search.
  useEffect(() => {
    if (searchTerm.trim().length < 2) {
      setSuggestions([]);
      return;
    }

    const controller = new AbortController();

    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/search?q=${encodeURIComponent(searchTerm.trim())}`,
          { signal: controller.signal }
        );

        if (res.ok) {
          const data = await res.json();
          setSuggestions(data.results || []);
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Autocomplete fetch error:', err);
        }
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchTerm]);

  // Load statistics when the app first mounts.
  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await fetch(`${API_BASE}/stats`);

        if (!res.ok) return;

        const data = await res.json();
        const savings = data.savings_ci;

        if (savings) {
          setMeanSavings(
            savings.mean_savings_pct != null
              ? `${savings.mean_savings_pct}%`
              : '--%'
          );

          setCiSavings(
            savings.ci_95_lower != null &&
            savings.ci_95_upper != null
              ? `(${savings.ci_95_lower}% - ${savings.ci_95_upper}%)`
              : '--'
          );
        }
      } catch (err) {
        console.error('Stats fetch error:', err);
      }
    }

    fetchStats();
  }, []);

  // Search for a medicine and load its substitutes.
  const handleSearch = async (medicineName: string) => {
    const cleanName = medicineName.trim();

    if (!cleanName || isSearching) return;

    setSearchTerm(cleanName);
    setSuggestions([]);
    setIsSearching(true);

    try {
      const res = await fetch(
        `${API_BASE}/recommend?name=${encodeURIComponent(cleanName)}&top=10`
      );

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);

        alert(
          errorData?.detail ||
            'Medicine not found in database. Please try another name.'
        );
        return;
      }

      const data: RecommendationResponse = await res.json();

      if (!data.query_drug || !Array.isArray(data.substitutes)) {
        alert('The server returned an unexpected response.');
        return;
      }

      setQueryResult(data);
      setExpandedRow(null);
      setSortBy('savings');
      setChatInput('');

      setChatMessages([
        {
          sender: 'bot',
          text: `I've analyzed the alternatives for ${data.query_drug.name}. Ask me about prices, potential savings, side-effect comparisons, or ranking metrics.`,
        },
      ]);
    } catch (err) {
      console.error('Search execution error:', err);
      alert('Unable to connect to the medicine database. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  // Send a question about the current medicine and its substitutes.
  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!chatInput.trim() || !queryResult || isChatLoading) return;

    const userQuery = chatInput.trim();

    setChatMessages((prev) => [
      ...prev,
      { sender: 'user', text: userQuery },
    ]);

    setChatInput('');
    setIsChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userQuery,
          query_drug: queryResult.query_drug,
          substitutes: sortedSubstitutes,
        }),
      });

      if (!res.ok) {
        throw new Error(`Chat request failed: ${res.status}`);
      }

      const data = await res.json();

      setChatMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text:
            data.explanation ||
            'Sorry, I could not generate an explanation.',
        },
      ]);
    } catch (err) {
      console.error('Chat request error:', err);

      setChatMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: 'Connection error while communicating with the AI assistant.',
        },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Safely display the comparison returned by the backend.
  const renderSideEffectComparison = (sub: Substitute) => {
    const comparison = sub.side_effect_comparison;

    if (!comparison || comparison.status === 'insufficient_data') {
      return (
        <div className="p-3 rounded bg-amber-950/30 border border-amber-800/40 text-amber-200">
          <strong className="block text-white mb-1">
            Side-effect Comparison
          </strong>
          {comparison?.message ||
            'Comparison data is unavailable. The side-effect records could not be compared reliably.'}
        </div>
      );
    }

    return (
      <div className="p-3 rounded bg-sage-950/60 border border-sage-500/20 text-sage-300 space-y-3">
        <strong className="block text-white">
          Side-effect Comparison
        </strong>

        <div>
          <span className="font-semibold text-white block mb-1">
            Listed for both
          </span>
          <p>
            {comparison.shared_effects.length > 0
              ? comparison.shared_effects.join(', ')
              : 'No matching terms were found in the recorded data.'}
          </p>
        </div>

        <div>
          <span className="font-semibold text-white block mb-1">
            Listed only for the substitute in this dataset
          </span>
          <p>
            {comparison.substitute_only_in_data.length > 0
              ? comparison.substitute_only_in_data.join(', ')
              : 'No additional terms were found in the recorded data.'}
          </p>
        </div>

        <div>
          <span className="font-semibold text-white block mb-1">
            Listed only for the original in this dataset
          </span>
          <p>
            {comparison.original_only_in_data.length > 0
              ? comparison.original_only_in_data.join(', ')
              : 'No additional terms were found in the recorded data.'}
          </p>
        </div>

        <p className="text-sage-400">
          {comparison.message}
        </p>
      </div>
    );
  };

  return (
    <div className="relative min-h-screen text-sage-100 bg-dark-bg font-sans selection:bg-sage-500 selection:text-black">
      {/* Sage Green Dynamic Canvas Wave */}
      <HeroWave className="fixed inset-0 w-full h-full pointer-events-none opacity-80 -z-10" />

      {/* Gradient Vignette Overlay */}
      <div className="fixed inset-0 bg-gradient-to-b from-black/70 via-black/50 to-black/90 pointer-events-none -z-10" />

      {/* Top Navbar */}
      <header className="flex flex-col sm:flex-row items-center justify-between px-8 py-4 border-b border-dark-border bg-dark-card/80 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <Pill className="h-6 w-6 text-sage-500" />
          <h1 className="text-xl font-bold tracking-tight text-white">
            Indian Drug Substitute
          </h1>
        </div>

        <div className="flex items-center gap-2 mt-2 sm:mt-0 px-3 py-1.5 rounded-md bg-amber-950/40 border border-amber-800/40 text-amber-300 text-xs font-medium">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
          <span>
            Informational only. Consult a doctor or pharmacist before
            switching medicines.
          </span>
        </div>
      </header>

      {/* Main Layout */}
      <div className="w-full max-w-[96vw] mx-auto px-4 sm:px-8 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Panel: Search and Results */}
        <main className="lg:col-span-8 xl:col-span-9 flex flex-col gap-6">
          {/* Search Card */}
          <section className="relative z-30 p-6 rounded-xl bg-dark-card/90 border border-dark-border shadow-xl backdrop-blur-sm">
            <h2 className="text-lg font-semibold text-white">
              Find Medicine Substitutes
            </h2>

            <p className="text-sm text-sage-300 mt-1">
              Search by brand name to view identical composition alternatives
              ranked by price savings and reliability.
            </p>

            <div className="relative mt-4 flex gap-3">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSearch(searchTerm);
                    }
                  }}
                  placeholder="Enter medicine name (e.g., Crocin Pain Relief, Augmentin)..."
                  className="w-full px-4 py-3 bg-black/60 border border-dark-border rounded-lg text-white placeholder-sage-400/60 focus:outline-none focus:border-sage-500 transition-colors"
                />

                {suggestions.length > 0 && (
                  <div className="absolute left-0 right-0 top-full mt-2 bg-dark-card border border-dark-border rounded-lg shadow-2xl overflow-hidden z-50 max-h-60 overflow-y-auto">
                    {suggestions.map((name, idx) => (
                      <button
                        key={`${name}-${idx}`}
                        type="button"
                        onClick={() => handleSearch(name)}
                        className="w-full text-left px-4 py-2.5 text-sm hover:bg-sage-900/60 text-sage-200 transition-colors border-b border-dark-border/50 last:border-none"
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => handleSearch(searchTerm)}
                disabled={isSearching}
                className="px-6 py-3 bg-sage-500 hover:bg-sage-600 disabled:opacity-60 text-black font-semibold rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-sage-500/10"
              >
                <Search className="h-4 w-4" />
                <span>{isSearching ? 'Searching...' : 'Search'}</span>
              </button>
            </div>
          </section>

          {/* Queried Medicine Summary */}
          {queryResult && (
            <section className="relative z-10 p-6 rounded-xl bg-sage-950/40 border border-sage-500/30 backdrop-blur-sm">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-sage-400">
                    Queried Medicine
                  </span>

                  <h3 className="text-xl font-bold text-white mt-0.5">
                    {queryResult.query_drug.name}
                  </h3>
                </div>

                <span className="px-3 py-1 rounded-full bg-sage-500/10 text-sage-300 border border-sage-500/20 text-xs font-medium">
                  {queryResult.query_drug.dosage_form}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4 pt-4 border-t border-sage-500/20 text-sm">
                <div>
                  <span className="text-sage-400 text-xs block">
                    Manufacturer
                  </span>

                  <span className="font-medium text-white flex items-center gap-1.5 mt-0.5">
                    <Building2 className="h-3.5 w-3.5 text-sage-500" />
                    {queryResult.query_drug.manufacturer}
                  </span>
                </div>

                <div>
                  <span className="text-sage-400 text-xs block">
                    Pack Price
                  </span>

                  <span className="font-medium text-white mt-0.5 block">
                    ₹{queryResult.query_drug.price_inr}{' '}
                    <span className="text-xs text-sage-400">
                      ({queryResult.query_drug.pack_size})
                    </span>
                  </span>
                </div>

                <div>
                  <span className="text-sage-400 text-xs block">
                    Unit Price
                  </span>

                  <span className="font-medium text-sage-300 mt-0.5 block">
                    ₹{queryResult.query_drug.price_per_unit} / unit
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-sage-500/20 text-xs">
                <span className="text-sage-400 block mb-1">
                  Active Composition
                </span>

                <code className="text-sage-200 bg-black/40 px-2.5 py-1 rounded border border-sage-500/20 inline-block font-mono">
                  {queryResult.query_drug.composition}
                </code>
              </div>
            </section>
          )}

          {/* Results Table */}
          {queryResult && (
            <section className="p-6 rounded-xl bg-dark-card/90 border border-dark-border shadow-xl backdrop-blur-sm">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-white">
                    Ranked Substitutes
                  </h3>

                  <p className="text-xs text-sage-300 mt-0.5">
                    Profile Match indicates similarity in the available
                    medicine data. Expand rows to view additional information.
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <label
                    htmlFor="sort-substitutes"
                    className="text-xs text-sage-300"
                  >
                    Sort by
                  </label>

                  <select
                    id="sort-substitutes"
                    value={sortBy}
                    onChange={(e) => {
                      setSortBy(e.target.value as SortOption);
                      setExpandedRow(null);
                    }}
                    className="px-3 py-2 rounded-lg bg-black/60 border border-dark-border text-sm text-sage-200 focus:outline-none focus:border-sage-500"
                  >
                    <option value="savings">Highest Savings</option>
                    <option value="price">Lowest Unit Price</option>
                    <option value="rating">Highest Medicine Match</option>
                  </select>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase bg-black/40 text-sage-400 border-b border-dark-border">
                    <tr>
                      <th className="py-3 px-4">Rank</th>
                      <th className="py-3 px-4">Substitute</th>
                      <th className="py-3 px-4">Pack Price</th>
                      <th className="py-3 px-4">Unit Price</th>
                      <th className="py-3 px-4">Savings</th>
                      <th className="py-3 px-4">Profile Match</th>
                      <th className="py-3 px-4">Action</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-dark-border">
                    {sortedSubstitutes.map((sub, index) => (
                      <React.Fragment key={`${sub.name}-${index}`}>
                        <tr className="hover:bg-sage-900/20 transition-colors">
                          <td className="py-4 px-4 font-semibold text-sage-400">
                            #{index + 1}
                          </td>

                          <td className="py-4 px-4">
                            <div className="font-medium text-white">
                              {sub.name}
                            </div>

                            <div className="text-xs text-sage-400">
                              {sub.manufacturer}
                            </div>
                          </td>

                          <td className="py-4 px-4 text-sage-200">
                            ₹{sub.price_inr}

                            <span className="block text-[10px] text-sage-400">
                              {sub.pack_size}
                            </span>
                          </td>

                          <td className="py-4 px-4 text-white font-medium">
                            ₹{sub.price_per_unit}
                          </td>

                          <td className="py-4 px-4">
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800/50">
                              <TrendingDown className="h-3.5 w-3.5" />
                              {sub.savings_pct}%
                            </span>
                          </td>

                          <td className="py-4 px-4 font-medium text-sage-300">
                            {sub.side_effect_similarity_pct}%
                          </td>

                          <td className="py-4 px-4">
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedRow(
                                  expandedRow === index ? null : index
                                )
                              }
                              aria-expanded={expandedRow === index}
                              className="px-3 py-1.5 text-xs font-medium rounded bg-sage-500/10 hover:bg-sage-500/20 text-sage-300 border border-sage-500/20 transition-colors flex items-center gap-1"
                            >
                              <span>Additional Information</span>

                              {expandedRow === index ? (
                                <ChevronUp className="h-3.5 w-3.5" />
                              ) : (
                                <ChevronDown className="h-3.5 w-3.5" />
                              )}
                            </button>
                          </td>
                        </tr>

                        {expandedRow === index && (
                          <tr className="bg-black/40">
                            <td
                              colSpan={7}
                              className="p-4 border-l-2 border-sage-500"
                            >
                              <div className="text-xs space-y-3 leading-relaxed text-sage-200">
                                <div>
                                  <span className="font-semibold text-white block mb-1">
                                    Active Ingredients
                                  </span>

                                  <span>
                                    {queryResult.query_drug.composition ||
                                      'Composition information is not available.'}
                                  </span>
                                </div>

                                <div className="space-y-3">
                                  <div>
                                    <span className="font-semibold text-white block mb-1">
                                      Original — {queryResult.query_drug.name}
                                    </span>

                                    <span>
                                      {queryResult.query_drug.side_effects ||
                                        'Side-effect information is not available in the dataset.'}
                                    </span>
                                  </div>

                                  <div>
                                    <span className="font-semibold text-white block mb-1">
                                      Substitute — {sub.name}
                                    </span>

                                    <span>
                                      {sub.side_effects ||
                                        'Side-effect information is not available in the dataset.'}
                                    </span>
                                  </div>

                                  {renderSideEffectComparison(sub)}
                                </div>

                                <div className="p-3 rounded bg-black/40 border border-dark-border text-sage-300">
                                  <strong className="text-white block mb-1">
                                    Price Trade-off
                                  </strong>

                                  The listed savings are {sub.savings_pct}%,
                                  with a unit price of ₹{sub.price_per_unit}
                                  compared with ₹
                                  {queryResult.query_drug.price_per_unit} per
                                  unit for {queryResult.query_drug.name}.
                                </div>

                                <p className="text-sage-400">
                                  Side-effect differences reflect the
                                  available data and do not prove that an
                                  effect is unique to either medicine.
                                  Confirm the ingredients, strength, dosage
                                  form, and suitability with a qualified
                                  pharmacist or doctor before switching.
                                </p>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              {sortedSubstitutes.length === 0 && (
                <p className="text-sm text-sage-400 py-4">
                  No substitutes were found for this medicine.
                </p>
              )}
            </section>
          )}

          {/* Market Statistics */}
          <section className="p-6 rounded-xl bg-dark-card/90 border border-dark-border backdrop-blur-sm">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-sage-500" />
              <span>Market Price Insights</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
              <div className="p-4 rounded-lg bg-black/40 border border-dark-border text-center">
                <span className="text-2xl font-bold text-sage-400">
                  {meanSavings}
                </span>

                <span className="text-xs text-sage-400 block mt-1">
                  Average Potential Savings
                </span>
              </div>

              <div className="p-4 rounded-lg bg-black/40 border border-dark-border text-center">
                <span className="text-2xl font-bold text-white">
                  {ciSavings}
                </span>

                <span className="text-xs text-sage-400 block mt-1">
                  95% Confidence Interval
                </span>
              </div>
            </div>
          </section>
        </main>

        {/* Right Panel: AI Chat Assistant */}
        <aside className="lg:col-span-4 xl:col-span-3 flex flex-col h-[calc(100vh-6rem)] min-h-0 sticky top-6">
          <div className="flex flex-1 min-h-0 flex-col overflow-hidden p-6 rounded-xl bg-dark-card/90 border border-dark-border shadow-xl backdrop-blur-sm">
            <div className="flex shrink-0 items-center gap-2 pb-4 border-b border-dark-border">
              <Bot className="h-5 w-5 text-sage-500" />

              <div>
                <h3 className="text-base font-semibold text-white">
                  AI Assistant
                </h3>

                <p className="text-xs text-sage-400">
                  Ask questions about ranked substitutes.
                </p>
              </div>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain my-4 space-y-3 pr-2">
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg text-xs leading-relaxed whitespace-pre-wrap break-words ${
                    msg.sender === 'user'
                      ? 'bg-sage-600 text-white ml-6'
                      : 'bg-black/50 text-sage-200 border border-dark-border mr-6'
                  }`}
                >
                  {msg.text.split('**').map((part, i) =>
                    i % 2 === 1 ? (
                      <strong key={i} className="text-white font-semibold">
                        {part}
                      </strong>
                    ) : (
                      part
                    )
                  )}
                </div>
              ))}

              {isChatLoading && (
                <div className="p-3 rounded-lg text-xs bg-black/50 text-sage-400 border border-dark-border mr-6 animate-pulse">
                  Analyzing medicine information...
                </div>
              )}
            </div>

            {/* Chat Input */}
            <form
              onSubmit={handleChatSubmit}
              className="flex shrink-0 gap-2 pt-2 border-t border-dark-border"
            >
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder={
                  queryResult
                    ? 'Ask about prices or side effects...'
                    : 'Search a medicine first...'
                }
                disabled={!queryResult || isChatLoading}
                className="flex-1 px-3 py-2 bg-black/60 border border-dark-border rounded-lg text-xs text-white placeholder-sage-400/60 focus:outline-none focus:border-sage-500 disabled:opacity-50"
              />

              <button
                type="submit"
                disabled={!queryResult || isChatLoading || !chatInput.trim()}
                className="px-3 py-2 bg-sage-500 hover:bg-sage-600 disabled:bg-sage-900 text-black rounded-lg transition-colors"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
