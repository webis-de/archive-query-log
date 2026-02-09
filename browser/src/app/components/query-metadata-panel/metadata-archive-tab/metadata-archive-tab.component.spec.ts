import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataArchiveTabComponent } from './metadata-archive-tab.component';
import { TranslateModule } from '@ngx-translate/core';

describe('MetadataArchiveTabComponent', () => {
  let component: MetadataArchiveTabComponent;
  let fixture: ComponentFixture<MetadataArchiveTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataArchiveTabComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataArchiveTabComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('archiveDetail', null);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
