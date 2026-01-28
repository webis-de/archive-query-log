export interface FilterState {
  dateFrom: string;
  dateTo: string;
  status: string;
  providers: string[];
  advancedMode?: boolean;
  fuzzy?: boolean;
  fuzziness?: 'AUTO' | '0' | '1' | '2';
  expandSynonyms?: boolean;
}

export interface FilterProvider {
  id: string;
  label: string;
  checked: boolean;
}
