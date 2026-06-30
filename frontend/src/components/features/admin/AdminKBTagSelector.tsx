'use client'

import { useId, useMemo, useState, type KeyboardEvent } from 'react'
import { Archive, Plus, X } from 'lucide-react'
import { cn } from '@/src/lib/utils/cn'
import type { KBMetadataTag } from '@/src/types/kb'

interface AdminKBTagSelectorProps {
  disabled?: boolean
  emptyMessage?: string
  label?: string
  onChange: (tagSlugs: string[]) => void
  placeholder?: string
  selectedSlugs: string[]
  tags: KBMetadataTag[]
}

export function AdminKBTagSelector({
  disabled = false,
  emptyMessage = 'No matching tags',
  label = 'Metadata tags',
  onChange,
  placeholder = 'Search preset tags',
  selectedSlugs,
  tags,
}: AdminKBTagSelectorProps) {
  const inputId = useId()
  const [query, setQuery] = useState('')
  const tagBySlug = useMemo(() => new Map(tags.map((tag) => [tag.slug, tag])), [tags])
  const normalizedQuery = query.trim().toLowerCase()
  const selectedSlugSet = useMemo(() => new Set(selectedSlugs), [selectedSlugs])
  const selectedTags = selectedSlugs.map((slug) => tagBySlug.get(slug) ?? tagFromUnknownSlug(slug))
  const suggestedTags = tags
    .filter((tag) => tag.is_active && !selectedSlugSet.has(tag.slug))
    .filter((tag) =>
      normalizedQuery
        ? tag.label.toLowerCase().includes(normalizedQuery) ||
          tag.slug.toLowerCase().includes(normalizedQuery)
        : true,
    )
    .slice(0, 8)

  const addTag = (slug: string) => {
    if (disabled || selectedSlugSet.has(slug)) return
    onChange([...selectedSlugs, slug])
    setQuery('')
  }

  const removeTag = (slug: string) => {
    if (disabled) return
    onChange(selectedSlugs.filter((selectedSlug) => selectedSlug !== slug))
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' || suggestedTags.length === 0) return
    event.preventDefault()
    addTag(suggestedTags[0].slug)
  }

  return (
    <div>
      <label className="pb-admin-kb-field-label block" htmlFor={inputId}>
        {label}
      </label>
      <input
        aria-describedby={`${inputId}-suggestions`}
        className="pb-admin-kb-input"
        disabled={disabled}
        id={inputId}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={handleInputKeyDown}
        placeholder={placeholder}
        value={query}
      />
      {selectedTags.length > 0 && (
        <div className="pb-admin-kb-selected-tags" aria-label="Selected metadata tags">
          {selectedTags.map((tag) => (
            <span className="pb-admin-kb-selected-tag" data-archived={!tag.is_active} key={tag.slug}>
              <span>{tag.label}</span>
              {!tag.is_active && (
                <span className="pb-admin-kb-tag-archived">
                  <Archive size={11} />
                  Archived
                </span>
              )}
              {!disabled && (
                <button
                  aria-label={`Remove ${tag.label}`}
                  className="pb-admin-kb-tag-icon"
                  onClick={() => removeTag(tag.slug)}
                  type="button"
                >
                  <X size={12} />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      <div className="pb-admin-kb-tag-suggestions" id={`${inputId}-suggestions`}>
        {suggestedTags.length > 0 ? (
          suggestedTags.map((tag) => (
            <span className="pb-admin-kb-tag-suggestion" key={tag.slug}>
              <span className="min-w-0 truncate">{tag.label}</span>
              <button
                aria-label={`Add ${tag.label}`}
                className="pb-admin-kb-tag-add"
                disabled={disabled}
                onClick={() => addTag(tag.slug)}
                type="button"
              >
                <Plus size={13} />
              </button>
            </span>
          ))
        ) : (
          <span className={cn('pb-admin-kb-tag-empty', disabled && 'opacity-60')}>
            {emptyMessage}
          </span>
        )}
      </div>
    </div>
  )
}

function tagFromUnknownSlug(slug: string): KBMetadataTag {
  return {
    id: slug,
    organization_id: '',
    slug,
    label: slug,
    sort_order: 0,
    is_active: false,
    created_at: '',
    updated_at: '',
  }
}
