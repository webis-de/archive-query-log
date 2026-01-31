import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ArchiveResultContentComponent } from './archive-result-content.component';
import { TranslateModule } from '@ngx-translate/core';

describe('ArchiveResultContentComponent', () => {
  let component: ArchiveResultContentComponent;
  let fixture: ComponentFixture<ArchiveResultContentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ArchiveResultContentComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(ArchiveResultContentComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('archive', { name: 'Test', id: '1', serp_count: 0 });
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
