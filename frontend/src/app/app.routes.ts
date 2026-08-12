import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'widget/:slug',
    loadComponent: () => import('./widget/widget-page').then(m => m.WidgetPage),
  },
  {
    path: 'admin',
    loadComponent: () => import('./admin/admin-page').then(m => m.AdminPage),
  },
  { path: '', pathMatch: 'full', redirectTo: 'widget/riviera' },
  { path: '**', redirectTo: 'widget/riviera' },
];
