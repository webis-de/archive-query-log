import { Directive, input, booleanAttribute } from '@angular/core';

@Directive({
  selector: '[aqlScrollbar]',
  standalone: true,
  host: {
    '[class.aql-scrollbar]': 'true',
    '[class.aql-scrollbar-slim]': 'slim()',
  },
})
export class AqlScrollbarDirective {
  readonly slim = input(false, { transform: booleanAttribute });
}
