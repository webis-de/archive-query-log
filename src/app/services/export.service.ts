import { Injectable } from '@angular/core';
import { from, Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class ExportService {
  copyToClipboard(text: string): Observable<void> {
    return from(navigator.clipboard.writeText(text));
  }

  downloadCsv<T extends Record<string, unknown>>(
    data: T[],
    filename: string,
    options?: { headers?: (keyof T)[] },
  ): void {
    if (!data || data.length === 0) {
      return;
    }

    const headers = (options?.headers ?? Object.keys(data[0])) as string[];
    const headerRow = headers.join(',');

    const rows = data
      .map(item => {
        return headers
          .map(header => {
            const val = item[header];
            const valStr = val === null || val === undefined ? '' : String(val);
            // Escape quotes
            const escaped = valStr.replace(/"/g, '""');
            // Wrap in quotes if it contains comma, newline or quote
            return `"${escaped}"`;
          })
          .join(',');
      })
      .join('\n');

    const csvContent = `\uFEFF${headerRow}\n${rows}`; // BOM for Excel
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    this.downloadBlob(blob, filename);
  }

  downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    this.downloadUrl(url, filename);
    URL.revokeObjectURL(url);
  }

  downloadUrl(url: string, filename: string): void {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // Helper to format generic data for clipboard copy
  formatAsTsv<T extends Record<string, unknown>>(data: T[], headers?: (keyof T)[]): string {
    if (!data || data.length === 0) {
      return '';
    }

    const cols = (headers ?? Object.keys(data[0])) as string[];
    const headerRow = cols.join('\t');
    const rows = data
      .map(item =>
        cols
          .map(col => {
            const val = item[col];
            return val === null || val === undefined ? '' : String(val);
          })
          .join('\t'),
      )
      .join('\n');

    return `${headerRow}\n${rows}`;
  }
}
