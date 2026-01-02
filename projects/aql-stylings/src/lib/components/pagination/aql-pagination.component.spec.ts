import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AqlPaginationComponent } from './aql-pagination.component';

import { AqlButtonComponent } from '../button/aql-button.component';

import { TranslateModule } from '@ngx-translate/core';

describe('AqlPaginationComponent', () => {
  let component: AqlPaginationComponent;

  let fixture: ComponentFixture<AqlPaginationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TranslateModule.forRoot(), AqlPaginationComponent, AqlButtonComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlPaginationComponent);

    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should calculate total pages correctly', () => {
    fixture.componentRef.setInput('totalItems', 100);

    fixture.componentRef.setInput('pageSize', 10);

    fixture.detectChanges();

    expect(component.totalPages()).toBe(10);
  });

  it('should emit page change event', () => {
    fixture.componentRef.setInput('totalItems', 100);

    fixture.componentRef.setInput('pageSize', 10);

    fixture.componentRef.setInput('currentPage', 1);

    fixture.detectChanges();

    let emittedPage: number | undefined;

    component.pageChange.subscribe(page => (emittedPage = page));

    component.goToPage(3);

    expect(emittedPage).toBe(3);
  });

  it('should navigate to next page', () => {
    fixture.componentRef.setInput('totalItems', 100);

    fixture.componentRef.setInput('pageSize', 10);

    fixture.componentRef.setInput('currentPage', 5);

    fixture.detectChanges();

    let emittedPage: number | undefined;

    component.pageChange.subscribe(page => (emittedPage = page));

    component.goToNextPage();

    expect(emittedPage).toBe(6);
  });
});
