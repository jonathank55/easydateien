#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) return 1;
        NSString *action = [NSString stringWithUTF8String:argv[1]];
        NSPasteboard *pb = [NSPasteboard generalPasteboard];

        if ([action isEqualToString:@"set"] && argc > 2) {
            [pb clearContents];

            NSMutableArray<NSString *> *paths = [NSMutableArray array];
            NSImage *firstImage = nil;
            BOOL hasImage = NO;

            for (int i = 2; i < argc; i++) {
                NSString *p = [NSString stringWithUTF8String:argv[i]];
                [paths addObject:p];

                if (!hasImage && (argc == 3)) {
                    NSString *ext = [[p pathExtension] lowercaseString];
                    if ([ext isEqualToString:@"png"] || [ext isEqualToString:@"jpg"] ||
                        [ext isEqualToString:@"jpeg"] || [ext isEqualToString:@"gif"] ||
                        [ext isEqualToString:@"tiff"] || [ext isEqualToString:@"tif"] ||
                        [ext isEqualToString:@"webp"] || [ext isEqualToString:@"heic"] ||
                        [ext isEqualToString:@"bmp"]) {
                        NSImage *img = [[NSImage alloc] initWithContentsOfFile:p];
                        if (img) {
                            hasImage = YES;
                            firstImage = img;
                        }
                    }
                }
            }

            NSMutableArray<NSPasteboardType> *types = [NSMutableArray arrayWithObjects:
                (NSPasteboardType)@"NSFilenamesPboardType",
                NSPasteboardTypeFileURL,
                NSPasteboardTypeString,
                nil
            ];

            NSData *pngData = nil;
            NSData *tiffData = nil;
            if (hasImage && firstImage) {
                NSRect r = NSMakeRect(0, 0, firstImage.size.width, firstImage.size.height);
                CGImageRef cgRef = [firstImage CGImageForProposedRect:&r context:nil hints:nil];
                if (cgRef) {
                    NSBitmapImageRep *rep = [[NSBitmapImageRep alloc] initWithCGImage:cgRef];
                    pngData = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
                    tiffData = [rep representationUsingType:NSBitmapImageFileTypeTIFF properties:@{}];
                    if (pngData) [types addObject:NSPasteboardTypePNG];
                    if (tiffData) [types addObject:NSPasteboardTypeTIFF];
                }
            }

            // Deklariere alle Typen gleichzeitig auf dem Pasteboard
            [pb declareTypes:types owner:nil];

            // 1. NSFilenamesPboardType (PropertyList für Finder, WhatsApp, Discord, Slack, VSCode)
            [pb setPropertyList:paths forType:(NSPasteboardType)@"NSFilenamesPboardType"];

            // 2. File URL (public.file-url für Mail, Safari, Finder)
            NSURL *firstUrl = [NSURL fileURLWithPath:paths[0]];
            if (firstUrl) {
                [pb setString:[firstUrl absoluteString] forType:NSPasteboardTypeFileURL];
            }

            // 3. Reiner Text (public.utf8-plain-text für Texteditoren und Terminals)
            NSString *allPaths = [paths componentsJoinedByString:@"\n"];
            [pb setString:allPaths forType:NSPasteboardTypeString];

            // 4. Bilddaten (PNG und TIFF für Grafik- und Chat-Programme)
            if (pngData) {
                [pb setData:pngData forType:NSPasteboardTypePNG];
            }
            if (tiffData) {
                [pb setData:tiffData forType:NSPasteboardTypeTIFF];
            }

            return 0;
        } else if ([action isEqualToString:@"get"]) {
            // 1. Zuerst NSFilenamesPboardType prüfen
            id filenames = [pb propertyListForType:(NSPasteboardType)@"NSFilenamesPboardType"];
            if ([filenames isKindOfClass:[NSArray class]] && [filenames count] > 0) {
                for (NSString *p in filenames) {
                    if ([p length] > 0) printf("%s\n", [p UTF8String]);
                }
                return 0;
            }

            // 2. NSURLs prüfen
            NSArray *classes = @[[NSURL class]];
            NSDictionary *options = @{NSPasteboardURLReadingFileURLsOnlyKey: @YES};
            NSArray *urls = [pb readObjectsForClasses:classes options:options];
            if (urls && [urls count] > 0) {
                for (NSURL *url in urls) {
                    printf("%s\n", [[url path] UTF8String]);
                }
                return 0;
            }

            // 3. Plain Text prüfen
            NSString *str = [pb stringForType:NSPasteboardTypeString];
            if (str && [str length] > 0) {
                printf("%s\n", [str UTF8String]);
            }
            return 0;
        }
    }
    return 0;
}
