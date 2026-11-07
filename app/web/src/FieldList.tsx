import { useEffect, useRef, useState } from "react";
import { FieldSummary } from "./api";
import { formatDate, formatHa } from "./App";

interface Props {
  fields: FieldSummary[];
  selectedId: number | null;
  onSelect: (field: FieldSummary) => void;
  onRename: (id: number, name: string) => void;
  onDelete: (field: FieldSummary) => void;
}

export default function FieldList({ fields, selectedId, onSelect, onRename, onDelete }: Props) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId != null) inputRef.current?.focus();
  }, [editingId]);

  if (fields.length === 0) return null;

  return (
    <ul className="fields">
      {fields.map((f) => {
        const active = f.id === selectedId;
        return (
          <li key={f.id} className={active ? "field-item active" : "field-item"}>
            {editingId === f.id ? (
              <form
                className="rename-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  const name = editName.trim();
                  if (name) onRename(f.id, name);
                  setEditingId(null);
                }}
              >
                <input
                  ref={inputRef}
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  aria-label="Neuer Feldname"
                  maxLength={120}
                />
                <button type="submit" className="icon-btn" title="Name speichern" aria-label="Name speichern">
                  ✓
                </button>
              </form>
            ) : (
              <>
                <button className="field-main" onClick={() => onSelect(f)}>
                  <span className="field-name">{f.name}</span>
                  <span className="field-meta">
                    {formatHa(f.area_m2)}
                    {f.last_obs ? ` · ${formatDate(f.last_obs)}` : " · noch nicht analysiert"}
                  </span>
                </button>
                <span className="field-actions">
                  <button
                    className="icon-btn"
                    title="Feld umbenennen"
                    aria-label={`${f.name} umbenennen`}
                    onClick={() => {
                      setEditName(f.name);
                      setEditingId(f.id);
                    }}
                  >
                    ✎
                  </button>
                  <button
                    className="icon-btn danger"
                    title="Feld löschen"
                    aria-label={`${f.name} löschen`}
                    onClick={() => onDelete(f)}
                  >
                    ✕
                  </button>
                </span>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
