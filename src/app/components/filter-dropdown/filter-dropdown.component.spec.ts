import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { FilterDropdownComponent } from './filter-dropdown.component';
import { TranslateModule } from '@ngx-translate/core';
import { ProviderDetail, ProviderService } from '../../services/provider.service';
import { of, throwError } from 'rxjs';

describe('FilterDropdownComponent', () => {
  let component: FilterDropdownComponent;
  let fixture: ComponentFixture<FilterDropdownComponent>;
  let providerServiceSpy: jasmine.SpyObj<ProviderService>;

  const mockProviders: ProviderDetail[] = [
    {
      id: 'google',
      name: 'Google',
      domains: ['google.com', 'google.de'],
      priority: 1,
      url_patterns: ['google.com/*'],
    },
    {
      id: 'bing',
      name: 'Bing',
      domains: ['bing.com', 'bing.de'],
      priority: 2,
      url_patterns: ['bing.com/*'],
    },
    {
      id: 'duckduckgo',
      name: 'DuckDuckGo',
      domains: ['duckduckgo.com', 'duckduckgo.de'],
      priority: 3,
      url_patterns: ['duckduckgo.com/*'],
    },
    {
      id: 'yahoo',
      name: 'Yahoo',
      domains: ['yahoo.com', 'yahoo.de'],
      priority: 4,
      url_patterns: ['yahoo.com/*'],
    },
    {
      id: 'yandex',
      name: 'Yandex',
      domains: ['yandex.com', 'yandex.de'],
      priority: 5,
      url_patterns: ['yandex.com/*'],
    },
    {
      id: 'baidu',
      name: 'Baidu',
      domains: ['baidu.com', 'baidu.de'],
      priority: 6,
      url_patterns: ['baidu.com/*'],
    },
    {
      id: 'ecosia',
      name: 'Ecosia',
      domains: ['ecosia.org', 'ecosia.de'],
      priority: 7,
      url_patterns: ['ecosia.org/*'],
    },
  ];

  beforeEach(async () => {
    providerServiceSpy = jasmine.createSpyObj('ProviderService', ['getProviders']);
    providerServiceSpy.getProviders.and.returnValue(of(mockProviders));

    await TestBed.configureTestingModule({
      imports: [FilterDropdownComponent, TranslateModule.forRoot()],
      providers: [{ provide: ProviderService, useValue: providerServiceSpy }],
    }).compileComponents();

    fixture = TestBed.createComponent(FilterDropdownComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load providers from service on init', fakeAsync(() => {
    tick();
    expect(providerServiceSpy.getProviders).toHaveBeenCalled();
    expect(component.providers().length).toBe(mockProviders.length + 1); // +1 for "All" option
  }));

  it('should include "All" option at the beginning of providers list', fakeAsync(() => {
    tick();
    const providers = component.providers();
    expect(providers[0].label).toBe('All');
    expect(providers[0].checked).toBeTrue();
  }));

  it('should render correct number of providers from API', fakeAsync(() => {
    tick();
    // Should have "All" + all mock providers
    expect(component.providers().length).toBe(8);
  }));

  it('should set loading state to false after providers load', fakeAsync(() => {
    tick();
    expect(component.isLoadingProviders()).toBeFalse();
  }));

  it('should handle provider load error gracefully', fakeAsync(() => {
    // Reset and create new component with error
    providerServiceSpy.getProviders.and.returnValue(throwError(() => new Error('API Error')));

    const newFixture = TestBed.createComponent(FilterDropdownComponent);
    const newComponent = newFixture.componentInstance;
    newFixture.detectChanges();
    tick();

    expect(newComponent.providerLoadError()).toBeTrue();
    expect(newComponent.isLoadingProviders()).toBeFalse();
    // Should have fallback "All" option
    expect(newComponent.providers().length).toBe(1);
    expect(newComponent.providers()[0].label).toBe('All');
  }));

  it('should filter providers based on search input', fakeAsync(() => {
    tick();
    component.updateProviderSearch('goo');

    const filtered = component.filteredProviders();
    // Should include "All" and "Google"
    expect(filtered.length).toBe(2);
    expect(filtered.some(p => p.label === 'Google')).toBeTrue();
    expect(filtered.some(p => p.label === 'All')).toBeTrue();
  }));

  it('should show all providers when search is empty', fakeAsync(() => {
    tick();
    component.updateProviderSearch('');

    const filtered = component.filteredProviders();
    expect(filtered.length).toBe(mockProviders.length + 1);
  }));

  it('should clear search on reset', fakeAsync(() => {
    tick();
    component.updateProviderSearch('test');
    expect(component.providerSearch()).toBe('test');

    component.reset();
    expect(component.providerSearch()).toBe('');
  }));

  it('should count selected providers correctly', fakeAsync(() => {
    tick();
    // Initially no providers selected (only "All" is checked)
    expect(component.selectedProviderCount()).toBe(0);

    // Select Google
    component.updateProviderCheckedByLabel('Google', true);
    expect(component.selectedProviderCount()).toBe(1);

    // Select Bing
    component.updateProviderCheckedByLabel('Bing', true);
    expect(component.selectedProviderCount()).toBe(2);
  }));

  it('should uncheck "All" when a specific provider is selected', fakeAsync(() => {
    tick();
    expect(component.providers().find(p => p.label === 'All')?.checked).toBeTrue();

    component.updateProviderCheckedByLabel('Google', true);

    expect(component.providers().find(p => p.label === 'All')?.checked).toBeFalse();
    expect(component.providers().find(p => p.label === 'Google')?.checked).toBeTrue();
  }));

  it('should check "All" and uncheck others when "All" is selected', fakeAsync(() => {
    tick();
    // First select some providers
    component.updateProviderCheckedByLabel('Google', true);
    component.updateProviderCheckedByLabel('Bing', true);

    // Now select "All"
    component.updateProviderCheckedByLabel('All', true);

    const providers = component.providers();
    expect(providers.find(p => p.label === 'All')?.checked).toBeTrue();
    expect(providers.find(p => p.label === 'Google')?.checked).toBeFalse();
    expect(providers.find(p => p.label === 'Bing')?.checked).toBeFalse();
  }));
});
