import { Routes } from '@angular/router';
import { SearchViewComponent } from './pages/search-view/search-view.component';
import { LandingComponent } from './pages/landing/landing.component';

export const routes: Routes = [
  { path: '', component: LandingComponent },
  { path: 'serps/search', component: SearchViewComponent },
  { path: '**', redirectTo: '' },
];
