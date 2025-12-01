import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppSidebarComponent } from './app-sidebar.component';
import { UserData } from '../../models/user-data.model';

const mockUserData: UserData = {
  user: {
    name: 'Test User',
    institute: 'Test Institute',
    avatarUrl: null,
  },
  projects: [
    {
      id: '1',
      name: 'Test Project',
      items: [
        { id: '1', name: 'Item 1' },
        { id: '2', name: 'Item 2' },
      ],
    },
  ],
};

describe('AppSidebarComponent', () => {
  let component: AppSidebarComponent;
  let fixture: ComponentFixture<AppSidebarComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppSidebarComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AppSidebarComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('userData', mockUserData);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should start in expanded state', () => {
    expect(component.isCollapsed()).toBe(false);
  });

  it('should toggle collapsed state', () => {
    component.toggleCollapsed();
    expect(component.isCollapsed()).toBe(true);

    component.toggleCollapsed();
    expect(component.isCollapsed()).toBe(false);
  });

  it('should set collapsed state with force parameter', () => {
    component.toggleCollapsed(true);
    expect(component.isCollapsed()).toBe(true);

    component.toggleCollapsed(false);
    expect(component.isCollapsed()).toBe(false);
  });

  it('should emit newProject event', () => {
    let emitted = false;
    component.newProject.subscribe(() => {
      emitted = true;
    });

    component.onNewProject();
    expect(emitted).toBe(true);
  });

  it('should have user data', () => {
    expect(component.userData()).toBeDefined();
    expect(component.userData().user).toBeDefined();
    expect(component.userData().projects).toBeDefined();
  });

  it('should return filtered projects', () => {
    const projects = component.filteredProjects();
    expect(projects).toBeDefined();
    expect(Array.isArray(projects)).toBe(true);
  });
});
