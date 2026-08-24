import React, { useState, useEffect, useRef } from 'react';
import { MapPin, X, Loader2 } from 'lucide-react';
import { searchPlaces } from '../api';
import type { LocationResult } from '../types';

export interface LocationAutocompleteProps {
  label?: string;
  placeholder?: string;
  value?: string;
  city?: string;
  sessionId?: string;
  token?: string;
  disabled?: boolean;
  onSelect: (location: LocationResult) => void;
  className?: string;
  iconType?: 'pickup' | 'destination';
}

export const LocationAutocomplete: React.FC<LocationAutocompleteProps> = ({
  label,
  placeholder = 'Tìm địa chỉ, địa danh...',
  value = '',
  city = 'Hà Nội',
  sessionId,
  token,
  disabled = false,
  onSelect,
  className = '',
  iconType = 'pickup',
}) => {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<LocationResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const timer = setTimeout(async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await searchPlaces(query, {
          city,
          sessionId,
          token,
          signal: controller.signal,
          limit: 5,
        });
        setResults(data);
        setIsOpen(true);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError('Không thể tìm địa điểm. Vui lòng thử lại.');
        }
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, city, sessionId, token]);

  const handleSelect = (item: LocationResult) => {
    setQuery(item.name || item.display_name);
    setIsOpen(false);
    onSelect(item);
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      {label && (
        <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        <div className="absolute left-3.5 flex items-center pointer-events-none">
          {iconType === 'pickup' ? (
            <div className="w-2.5 h-2.5 rounded-full bg-[#00C9B7] ring-4 ring-[#00C9B7]/20" />
          ) : (
            <div className="w-2.5 h-2.5 rounded-full bg-red-500 ring-4 ring-red-500/20" />
          )}
        </div>

        <input
          type="text"
          value={query}
          disabled={disabled}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          placeholder={placeholder}
          className="w-full bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700/60 rounded-xl pl-9 pr-9 py-2.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#00C9B7] focus:border-transparent transition-all shadow-sm"
        />

        <div className="absolute right-3 flex items-center space-x-1">
          {isLoading && <Loader2 className="w-4 h-4 text-[#00C9B7] animate-spin" />}
          {query && !isLoading && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-full transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && (results.length > 0 || error) && (
        <div className="absolute z-[2000] w-full mt-1.5 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-xl shadow-xl overflow-hidden max-h-64 overflow-y-auto">
          {error && <div className="p-3 text-xs text-red-500">{error}</div>}
          {results.map((item, idx) => (
            <button
              key={item.id || item.provider_place_id || idx}
              type="button"
              onClick={() => handleSelect(item)}
              className="w-full px-3.5 py-2.5 text-left flex items-start space-x-2.5 hover:bg-gray-50 dark:hover:bg-gray-700/50 border-b border-gray-50 dark:border-gray-700/30 last:border-none transition-colors"
            >
              <MapPin className="w-4 h-4 text-[#00C9B7] mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                  {item.name || item.display_name.split(',')[0]}
                </div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400 truncate mt-0.5">
                  {item.formatted_address || item.display_name}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
