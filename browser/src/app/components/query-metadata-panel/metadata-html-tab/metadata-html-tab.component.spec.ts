import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataHtmlTabComponent } from './metadata-html-tab.component';
import { TranslateModule } from '@ngx-translate/core';

describe('MetadataHtmlTabComponent', () => {
  let component: MetadataHtmlTabComponent;
  let fixture: ComponentFixture<MetadataHtmlTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataHtmlTabComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataHtmlTabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
