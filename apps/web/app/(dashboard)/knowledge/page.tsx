"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, getToken } from "@/lib/auth";
import { API_BASE_URL } from "@/lib/config";
import { EmptyState } from "@/components/EmptyState";

interface DocumentResponse {
  id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  processing_status: "uploaded" | "processing" | "ready" | "failed" | "archived";
  processing_error: string | null;
  uploaded_at: string;
}

interface PaginatedDocuments {
  items: DocumentResponse[];
  total: number;
}

interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  chunk_index: number;
  content: string;
  similarity: number;
}

interface RagAnswer {
  answer: string;
  confidence: number;
  citations: { document_title: string; chunk_index: number }[];
  insufficient_evidence: boolean;
  model_name: string;
}

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  uploaded: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  processing: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  archived: "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500",
};

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<DocumentResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [asking, setAsking] = useState(false);

  const load = useCallback(() => {
    apiFetch<PaginatedDocuments>("/v1/documents?page_size=50")
      .then((res) => setDocuments(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load documents."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getToken();
      const response = await fetch(`${API_BASE_URL}/v1/documents`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!response.ok && response.status !== 409) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : `Upload failed (${response.status})`);
      }
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function runSearch() {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const results = await apiFetch<SearchResult[]>(
        `/v1/knowledge/search?query=${encodeURIComponent(query)}`,
      );
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  async function runAsk() {
    if (!question.trim()) return;
    setAsking(true);
    setError(null);
    setAnswer(null);
    try {
      const result = await apiFetch<RagAnswer>("/v1/knowledge/ask", {
        method: "POST",
        body: JSON.stringify({ question }),
      });
      setAnswer(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask failed.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="flex flex-col gap-8 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Knowledge</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Upload company documents (policies, pricing sheets, FAQs) so the Assistant can ground its replies
          in them. Every answer below is generated only from what&rsquo;s actually in these documents — if
          there isn&rsquo;t enough information, it says so instead of guessing.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
        <h2 className="text-sm font-medium mb-3">Documents</h2>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md,.csv"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
          }}
          className="text-sm mb-4"
        />

        {documents === null && <p className="text-sm text-zinc-500">Loading…</p>}
        {documents !== null && documents.length === 0 && (
          <EmptyState
            title="No documents yet"
            description="Upload a PDF, DOCX, TXT, Markdown, or CSV file to start building the knowledge base."
          />
        )}
        {documents !== null && documents.length > 0 && (
          <ul className="flex flex-col gap-2">
            {documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between text-sm border-b border-zinc-100 dark:border-zinc-900 pb-2"
              >
                <span>{doc.original_filename}</span>
                <span className={`text-xs rounded px-2 py-0.5 ${STATUS_STYLES[doc.processing_status]}`}>
                  {doc.processing_status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
        <h2 className="text-sm font-medium mb-3">Search</h2>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            placeholder="e.g. refund policy"
            className="flex-1 rounded border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-1.5 text-sm"
          />
          <button
            onClick={runSearch}
            disabled={searching}
            className="rounded bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            Search
          </button>
        </div>
        {searchResults !== null && (
          <ul className="mt-4 flex flex-col gap-3">
            {searchResults.length === 0 && <p className="text-sm text-zinc-500">No matches.</p>}
            {searchResults.map((r) => (
              <li key={r.chunk_id} className="text-sm">
                <div className="flex justify-between text-xs text-zinc-500 mb-1">
                  <span>{r.document_title}</span>
                  <span>similarity {r.similarity.toFixed(2)}</span>
                </div>
                <p className="text-zinc-700 dark:text-zinc-300">{r.content}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
        <h2 className="text-sm font-medium mb-3">Ask</h2>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runAsk()}
            placeholder="Ask a question grounded in your documents"
            className="flex-1 rounded border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-1.5 text-sm"
          />
          <button
            onClick={runAsk}
            disabled={asking}
            className="rounded bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            Ask
          </button>
        </div>
        {answer && (
          <div className="mt-4 text-sm">
            <p className="text-zinc-700 dark:text-zinc-300">{answer.answer}</p>
            <div className="mt-2 flex gap-3 text-xs text-zinc-500">
              <span>confidence {answer.confidence.toFixed(2)}</span>
              {answer.insufficient_evidence && <span className="text-amber-600">insufficient evidence</span>}
            </div>
            {answer.citations.length > 0 && (
              <ul className="mt-2 text-xs text-zinc-500 list-disc list-inside">
                {answer.citations.map((c, i) => (
                  <li key={i}>
                    {c.document_title} (chunk {c.chunk_index})
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
