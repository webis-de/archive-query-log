export interface FilterState {
  dateFrom: string;
  dateTo: string;
  status: string;
  providers: string[];
  advancedMode?: boolean;
}

export interface FilterProvider {
  id: string;
  label: string;
  checked: boolean;
}
