export interface FilterState {
  dateFrom: string;
  dateTo: string;
  status: string;
  providers: string[];
}

export interface Provider {
  id: string;
  label: string;
  checked: boolean;
}
