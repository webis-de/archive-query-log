import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TranslateModule } from '@ngx-translate/core';
import { AppSidebarComponent } from './app-sidebar.component';
import { provideRouter } from '@angular/router';
import { SessionService } from '../../services/session.service';
import { signal } from '@angular/core';

describe('AppSidebarComponent', () => {
  let component: AppSidebarComponent;
  let fixture: ComponentFixture<AppSidebarComponent>;
  let mockSessionService: {
    sidebarCollapsed: ReturnType<typeof signal<boolean>>;
    setSidebarCollapsed: jasmine.Spy;
  };

  beforeEach(async () => {
    // Create a mock service with signals
    const sidebarCollapsedSignal = signal(false);
    mockSessionService = {
      sidebarCollapsed: sidebarCollapsedSignal,
      setSidebarCollapsed: jasmine.createSpy('setSidebarCollapsed').and.callFake((val: boolean) => {
        sidebarCollapsedSignal.set(val);
      }),
    };

    await TestBed.configureTestingModule({
      imports: [AppSidebarComponent, TranslateModule.forRoot()],
      providers: [provideRouter([]), { provide: SessionService, useValue: mockSessionService }],
    }).compileComponents();

    fixture = TestBed.createComponent(AppSidebarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should start in default state', () => {
    expect(component.isCollapsed()).toBe(false);
  });

  it('should toggle collapsed state', () => {
    // Initial state is false
    component.toggleCollapsed();
    expect(mockSessionService.setSidebarCollapsed).toHaveBeenCalledWith(true);
    expect(component.isCollapsed()).toBe(true);

    component.toggleCollapsed();
    expect(mockSessionService.setSidebarCollapsed).toHaveBeenCalledWith(false);
    expect(component.isCollapsed()).toBe(false);
  });

  it('should set collapsed state with force parameter', () => {
    component.toggleCollapsed(true);
    expect(mockSessionService.setSidebarCollapsed).toHaveBeenCalledWith(true);
    expect(component.isCollapsed()).toBe(true);

    component.toggleCollapsed(false);
    expect(mockSessionService.setSidebarCollapsed).toHaveBeenCalledWith(false);
    expect(component.isCollapsed()).toBe(false);
  });
});
