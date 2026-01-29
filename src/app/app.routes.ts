import { Routes } from '@angular/router';
import { SearchViewComponent } from './pages/serp-search-view/search-view.component';
import { LandingComponent } from './pages/landing/landing.component';
import { ProviderSearchViewComponent } from './pages/provider-search-view/provider-search-view.component';
import { ArchiveSearchViewComponent } from './pages/archive-search-view/archive-search-view.component';

export const routes: Routes = [
  { path: '', component: LandingComponent },
  {
    path: 'serps/:id',
    component: SearchViewComponent,
    runGuardsAndResolvers: 'paramsOrQueryParamsChange',
  },
  { path: 'serps', component: SearchViewComponent },
  {
    path: 'providers/:id',
    component: ProviderSearchViewComponent,
    runGuardsAndResolvers: 'paramsOrQueryParamsChange',
  },
  { path: 'providers', component: ProviderSearchViewComponent },
  {
    path: 'archives/:id',
    component: ArchiveSearchViewComponent,
    runGuardsAndResolvers: 'paramsOrQueryParamsChange',
  },
  { path: 'archives', component: ArchiveSearchViewComponent },
  { path: '**', redirectTo: '' },
];
