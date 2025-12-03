import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';
import { LandingComponent } from './landing.component';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';

describe('LandingComponent', () => {
  let component: LandingComponent;
  let fixture: ComponentFixture<LandingComponent>;
  let mockRouter: jasmine.SpyObj<Router>;
  let mockActivatedRoute: jasmine.SpyObj<ActivatedRoute>;
  let mockSearchHistoryService: jasmine.SpyObj<SearchHistoryService>;
  let mockProjectService: jasmine.SpyObj<ProjectService>;
  let mockSessionService: jasmine.SpyObj<SessionService>;

  beforeEach(async () => {
    mockRouter = jasmine.createSpyObj('Router', ['navigate']);
    mockActivatedRoute = jasmine.createSpyObj('ActivatedRoute', [], {
      queryParams: of({}),
    });
    mockSearchHistoryService = jasmine.createSpyObj('SearchHistoryService', ['addSearch']);
    mockProjectService = jasmine.createSpyObj('ProjectService', [], {
      projects: jasmine.createSpy().and.returnValue([]),
    });
    mockSessionService = jasmine.createSpyObj('SessionService', [], {
      session: jasmine.createSpy().and.returnValue(null),
    });

    await TestBed.configureTestingModule({
      imports: [LandingComponent],
      providers: [
        { provide: Router, useValue: mockRouter },
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: SearchHistoryService, useValue: mockSearchHistoryService },
        { provide: ProjectService, useValue: mockProjectService },
        { provide: SessionService, useValue: mockSessionService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LandingComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize with empty search query', () => {
    expect(component.searchQuery()).toBe('');
  });

  it('should not navigate when search query is empty', () => {
    component.searchQuery.set('');
    component.onSearch();
    expect(mockRouter.navigate).not.toHaveBeenCalled();
  });

  it('should navigate to search when query is provided', () => {
    const mockSearchItem = {
      id: 'test-id',
      projectId: 'project-1',
      filter: { query: 'test query' },
      createdAt: new Date().toISOString(),
      label: 'test query',
    };
    mockSearchHistoryService.addSearch.and.returnValue(mockSearchItem);

    component.searchQuery.set('test query');
    component.onSearch();

    expect(mockSearchHistoryService.addSearch).toHaveBeenCalledWith({ query: 'test query' });
    expect(mockRouter.navigate).toHaveBeenCalledWith(['/s', 'test-id']);
  });

  it('should navigate to temporary search in temp mode', () => {
    component.isTemporaryMode.set(true);
    component.searchQuery.set('temp query');
    component.onSearch();

    expect(mockRouter.navigate).toHaveBeenCalledWith(['/s', 'temp'], {
      queryParams: { q: 'temp query' },
    });
  });

  it('should display correct landing message when no projects exist', () => {
    expect(component.landingMessage()).toBe('Create your first project and start searching');
  });
});
