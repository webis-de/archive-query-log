import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlTabMenuComponent, TabItem } from './aql-tab-menu.component';

describe('AqlTabMenuComponent', () => {
  let component: AqlTabMenuComponent;
  let fixture: ComponentFixture<AqlTabMenuComponent>;

  const mockTabs: TabItem[] = [
    { id: 'tab1', label: 'Tab 1' },
    { id: 'tab2', label: 'Tab 2', icon: 'bi-house' },
    { id: 'tab3', label: 'Tab 3', disabled: true },
    { id: 'tab4', label: 'Tab 4', badge: 5 },
  ];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlTabMenuComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlTabMenuComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('tabs', mockTabs);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render all tabs', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const tabs = compiled.querySelectorAll('[role="tab"]');
    expect(tabs.length).toBe(mockTabs.length);
  });

  it('should apply active class to active tab', () => {
    fixture.componentRef.setInput('activeTabId', 'tab1');
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const activeTab = compiled.querySelector('.tab-active');
    expect(activeTab?.textContent).toContain('Tab 1');
  });

  it('should apply disabled class to disabled tab', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const tabs = compiled.querySelectorAll('[role="tab"]');
    const disabledTab = Array.from(tabs).find(tab => tab.getAttribute('aria-disabled') === 'true');
    expect(disabledTab).toBeTruthy();
    expect(disabledTab?.classList.contains('tab-disabled')).toBe(true);
  });

  it('should emit tabChange event when tab is clicked', () => {
    let emittedTabId: string | undefined;
    component.tabChange.subscribe((tabId: string) => {
      emittedTabId = tabId;
    });

    component.onTabClick(mockTabs[0]);
    expect(emittedTabId).toBe('tab1');
  });

  it('should not emit tabChange event when disabled tab is clicked', () => {
    let emitCount = 0;
    component.tabChange.subscribe(() => {
      emitCount++;
    });

    component.onTabClick(mockTabs[2]); // disabled tab
    expect(emitCount).toBe(0);
  });

  it('should render icon when provided', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const iconTab = Array.from(compiled.querySelectorAll('[role="tab"]')).find(
      tab => tab.querySelector('i.bi-house')
    );
    expect(iconTab).toBeTruthy();
  });

  it('should render badge when provided', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const badgeTab = Array.from(compiled.querySelectorAll('[role="tab"]')).find(
      tab => tab.querySelector('.badge')
    );
    expect(badgeTab).toBeTruthy();
    expect(badgeTab?.textContent).toContain('5');
  });

  it('should apply size classes correctly', () => {
    fixture.componentRef.setInput('size', 'lg');
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const tablist = compiled.querySelector('[role="tablist"]');
    expect(tablist?.classList.contains('tabs-lg')).toBe(true);
  });

  it('should apply style classes correctly', () => {
    fixture.componentRef.setInput('tabStyle', 'boxed');
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const tablist = compiled.querySelector('[role="tablist"]');
    expect(tablist?.classList.contains('tabs-boxed')).toBe(true);
  });

  it('should apply full width when enabled', () => {
    fixture.componentRef.setInput('fullWidth', true);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const tabs = compiled.querySelectorAll('[role="tab"]');
    tabs.forEach(tab => {
      expect(tab.classList.contains('w-full')).toBe(true);
    });
  });
});
