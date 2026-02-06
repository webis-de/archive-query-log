import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataUnfurlTabComponent } from './metadata-unfurl-tab.component';
import { TranslateModule } from '@ngx-translate/core';

describe('MetadataUnfurlTabComponent', () => {
  let component: MetadataUnfurlTabComponent;
  let fixture: ComponentFixture<MetadataUnfurlTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataUnfurlTabComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataUnfurlTabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
