export interface FilterState {
  year?: number;
  status: string;
  provider?: string; // Single provider ID, undefined means no filter (all providers)
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
