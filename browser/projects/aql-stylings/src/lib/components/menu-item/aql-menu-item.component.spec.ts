import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { AqlMenuItemComponent } from './aql-menu-item.component';

@Component({
  standalone: true,
  imports: [AqlMenuItemComponent],
  template: `<aql-menu-item>Item Label</aql-menu-item>`,
})
class MenuItemWithLabelComponent {}

@Component({
  standalone: true,
  imports: [AqlMenuItemComponent],
  template: `<aql-menu-item><span after class="after-projected">Action</span></aql-menu-item>`,
})
class MenuItemWithAfterContentComponent {}

describe('AqlMenuItemComponent', () => {
  let fixture: ComponentFixture<AqlMenuItemComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlMenuItemComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlMenuItemComponent);
    fixture.detectChanges();
  });

  it('should render projected label', () => {
    const labelFixture = TestBed.createComponent(MenuItemWithLabelComponent);
    labelFixture.detectChanges();
    const label = labelFixture.debugElement.query(By.css('div span span'));
    expect(label.nativeElement.textContent.trim()).toBe('Item Label');
  });

  it('should render iconBefore when provided', () => {
    fixture.componentRef.setInput('iconBefore', 'bi-plus');
    fixture.detectChanges();
    const icon = fixture.debugElement.query(By.css('div i.bi-plus'));
    expect(icon).toBeTruthy();
  });

  it('should render iconAfter when provided', () => {
    fixture.componentRef.setInput('iconAfter', 'bi-chevron-right');
    fixture.detectChanges();
    const icon = fixture.debugElement.query(By.css('.after-slot i.bi-chevron-right'));
    expect(icon).toBeTruthy();
  });

  it('should render projected after content', () => {
    const afterFixture = TestBed.createComponent(MenuItemWithAfterContentComponent);
    afterFixture.detectChanges();
    const afterContent = afterFixture.debugElement.query(By.css('.after-slot .after-projected'));
    expect(afterContent.nativeElement.textContent.trim()).toBe('Action');
  });
});
