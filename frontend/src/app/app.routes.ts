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
  {
    path: 'app-demo',
    loadComponent: () => import('./app-demo/app-demo-page').then(m => m.AppDemoPage),
  },
  { path: '', pathMatch: 'full', redirectTo: 'widget/riviera' },
  { path: '**', redirectTo: 'widget/riviera' },
];
