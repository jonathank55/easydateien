#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) return 1;
        NSString *action = [NSString stringWithUTF8String:argv[1]];
        NSPasteboard *pb = [NSPasteboard generalPasteboard];

        if ([action isEqualToString:@"set"] && argc > 2) {
            [pb clearContents];
            NSMutableArray *urls = [NSMutableArray array];
            NSMutableArray *paths = [NSMutableArray array];
            for (int i = 2; i < argc; i++) {
                NSString *p = [NSString stringWithUTF8String:argv[i]];
                NSURL *url = [NSURL fileURLWithPath:p];
                if (url) {
                    [urls addObject:url];
                    [paths addObject:p];
                }
            }
            if ([urls count] > 0) {
                // 1. Write native file URLs for macOS Finder, Desktop, Mail etc.
                [pb writeObjects:urls];
                // 2. Write plain text representation for text editors and terminals
                NSString *allPaths = [paths componentsJoinedByString:@"\n"];
                [pb setString:allPaths forType:NSPasteboardTypeString];
            }
            return 0;
        } else if ([action isEqualToString:@"get"]) {
            // Read file URLs first
            NSArray *classes = @[[NSURL class]];
            NSDictionary *options = @{NSPasteboardURLReadingFileURLsOnlyKey: @YES};
            NSArray *urls = [pb readObjectsForClasses:classes options:options];
            if (urls && [urls count] > 0) {
                for (NSURL *url in urls) {
                    printf("%s\n", [[url path] UTF8String]);
                }
                return 0;
            }
            // Fallback to plain text if paths exist
            NSString *str = [pb stringForType:NSPasteboardTypeString];
            if (str && [str length] > 0) {
                printf("%s\n", [str UTF8String]);
            }
            return 0;
        }
    }
    return 0;
}
